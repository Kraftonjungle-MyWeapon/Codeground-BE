from typing import Tuple, List
from fastapi import APIRouter, HTTPException, WebSocket, Query, Depends
from starlette.websockets import WebSocketDisconnect
import asyncio
from src.app.domain.custom_room.crud import custom_room_crud as crud
from src.app.domain.custom_room.schemas.custom_room_schema import UserState, CustomRoom, RoomCreateRequest, ResponseRoom
from src.app.utils.logging import logger
from src.app.utils.s3_utils import issue_problem_urls
import json
from src.app.utils.game_session import custom_game_rooms
from sqlalchemy.orm import Session
from src.app.core.database import get_db
from typing import Annotated
router = APIRouter()
DB = Annotated[Session, Depends(get_db)]
RECONNECT_TIMEOUT = 2

@router.post("/create_room/{user_id}")
async def create_room(db:DB,room : RoomCreateRequest, user_id : int):
    room_id = await crud.alloc_room_id()

    title = room.title
    category = room.category
    difficulty = room.difficulty
    lang = room.use_language
    maker = await crud.make_user_state(db,user_id)
    new_room = CustomRoom(room_id = room_id,
                          title = title,
                          category=category,
                          use_language=lang,
                          difficulty=difficulty,
                          user= None,
                          maker=maker,
                          is_gaming=False)
    await crud.send_room_info(new_room)
    return {"room_id": room_id, "result": "ok"}

@router.get("/get_room/{room_id}", response_model=CustomRoom)
async def get_room(room_id: int) -> CustomRoom:
    room = await crud.get_room_info(room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    return room

@router.patch("/join_room/{room_id}/{user_id}", response_model=CustomRoom)
async def join_room(db:DB,room_id : int, user_id : int):
    return await crud.join_to_room(db,room_id, user_id)

@router.patch("/leave_room/{room_id}/{user_id}")
async def leave_room(room_id : int, user_id : int):
    await crud.leave_from_room(room_id, user_id)
    return {"result": "ok"}


@router.post("/update_room/{room_id}/{user_id}")
async def update_room(room_id : int, user_id : int,update_data: dict):
    new_room = await crud.edit_room(room_id, user_id, update_data)
    return new_room

@router.get("/rooms/{page}")
async def get_rooms(page : int) -> List[ResponseRoom]:
    return await crud.get_rooms_by_list(page)

# @router.patch("/start_room/{room_id}/{user_id}")
# async def start_room(db : DB,room_id : int, user_id : int):
#     await crud.start_game(room_id)


@router.websocket("/ws/custom_match/{room_id}")
async def room_websocket(db: DB,websocket: WebSocket, room_id: int, user_id: int = Query(...)):
    room = await crud.get_room_info(room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    user_id = int(user_id)
    logger.info(f"Attempting to accept WebSocket connection for user {user_id} in room {room_id}") # 이 줄 추가
    try:
        await websocket.accept()
    except RuntimeError as e:
        print(f"[WebSocket] accept() 실패: {e}")
        return

    logger.info(f"WebSocket connection attempt: user_id={user_id}, room_id={room_id}")
    logger.info(f"Room maker_id={room.maker.user_id}, room user_id={room.user.user_id if room.user else 'None'}")



    # 인증 : 해당 사설방 정보에 적혀있는 유저인지 확인
    if user_id != room.maker.user_id and (room.user and user_id != room.user.user_id):
        logger.warning(f"Unauthorized connection attempt by user {user_id} to custom_match {room_id}")
        await websocket.accept()
        await websocket.close(code=4001)
        return



# 재연결 감지 및 알림
    if ((room.user and room.user.user_id == user_id and not room.user.connected) or
            (room.maker and room.maker.user_id == user_id and not room.maker.connected)):
        await crud.connect_user(room.room_id, user_id)
        await crud.publish_to_custom_room(
            room_id,
            {"type": "opponent_rejoined", "user_id": user_id}
        )

    await crud.connect_user(room.room_id, user_id)

    if room.room_id not in custom_game_rooms:
        custom_game_rooms[room.room_id] = []
    custom_game_rooms[room.room_id].append(websocket)

    try:
        while True:
            message = await websocket.receive_text()
            logger.debug(f"Received message from user {user_id} in custom match {room_id}: {message}")
            await handle_custom_match_message(db,websocket, room_id, user_id, message)

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected from custom_match {room_id}")

        if websocket in custom_game_rooms.get(room_id, []):
            custom_game_rooms[room_id].remove(websocket)

        async def delayed_leave():
            updated_room = await crud.get_room_info(room_id)
            if updated_room is None:
                return
            # 유저/상대 판별
            (current_user, opponent) = await define_users(room_id, user_id)
            if updated_room.is_gaming:
                # 게임 중 이탈 시
                await asyncio.sleep(RECONNECT_TIMEOUT)
                await crud.process_custom_result(room_id, opponent.user_id, "abandon")
                await crud.leave_from_room(room_id, user_id)
                await crud.end_game(room_id)
            else:
                await crud.leave_from_room(room_id, user_id)
                # 필요하면 상대에게도 알림
                if opponent and opponent.connected:
                    await crud.publish_to_custom_room(
                        room_id,
                        {
                            "type": "opponent_left_waiting",
                            "user_id": user_id,
                            "room_id": room_id,
                            "message": "상대방이 대기실을 떠났습니다.",
                        },
                    )
        asyncio.create_task(delayed_leave())

async def handle_custom_match_message(db : Session,websocket : WebSocket, room_id : int, user_id : int , message : str):
    (current_user, opponent) = await define_users(room_id, user_id)
    try:
        data = json.loads(message)
        message_type = data.get("type")
        logger.info(f"Handling message type '{message_type}' for user {user_id} in game {room_id}")


        if message_type == "chat":
            # 채팅 메시지 전체 브로드캐스트
            await crud.publish_to_custom_room(room_id, {"type": "chat", "sender": user_id, "message": data.get("message")})

        elif message_type == "webrtc_signal":
            logger.debug(f"Broadcasting WebRTC signal from {user_id} in custom match {room_id}")
            # ICE candidate 혹은 SDP 교환
            await crud.publish_to_custom_room(room_id, {"type": "webrtc_signal", "sender": user_id, "signal": data.get("signal")})

        elif message_type == "custom_ready":
            ready = await crud.ready_user(room_id, user_id)
            await crud.publish_to_custom_room(room_id, {"type": "user_update_ready", "ready": ready})
            logger.info(f"User {user_id} is ready in custom match {room_id}")

        elif message_type == "ready":
            await crud.screen_share_ready(room_id, user_id)
            await crud.publish_to_custom_room(room_id, {"type": "player_ready", "user_id": user_id})
            logger.info(f"User {user_id} is ready in custom match screen share {room_id}")
            if opponent.screen_sharing_ready:
                logger.info(f"All players are ready in custom match {room_id}")
                await crud.publish_to_custom_room(room_id, {"type": "all_ready"})

        # 게임 타이머 시작 필요
        elif message_type == "game_start":
            await crud.publish_to_custom_room(room_id, {"type": "game_start"})
            problem_info = await crud.get_random_problem(db, room_id)
            presigned = await issue_problem_urls(problem_info)
            await crud.start_game(room_id)
            msg = {
                "type": "get_problem",
                "problem": {
                    "problem_id": problem_info.problem_id,
                    "problem_url": presigned["problem_url"],
                    "image_urls": presigned["image_urls"],
                    "difficulty": problem_info.difficulty,
                },
            }
            await crud.publish_to_custom_room(room_id, msg)
            logger.info(f"Custom match {room_id} is started")

        elif message_type == "system_warning":
            await crud.publish_to_custom_room(room_id,{
                "type": "system_warning",
                "event": data.get("event"),
                "count": data.get("count"),
                "message": data.get("message"),
                "user_id": user_id,  # 누가 보낸 건지 구분용
            })

        elif message_type == "screen_share_stopped":
            await crud.screen_share_stopped(room_id, user_id)
            logger.info(f"Screen share stopped by user {user_id} in custom match {room_id}")
            # 상대방에게 화면 공유 중단 알림 전송
            await crud.publish_to_custom_room(room_id,{
                    "type": "screen_share_stopped",
                    "user_id": user_id,
                    "message": "화면 공유가 중지되었습니다.",
                })
            #게임 타이머 중단 필요
            
        elif message_type == "screen_share_started":
            await crud.screen_share_started(room_id, user_id)
            logger.info(f"Screen share started by user {user_id} in custom match {room_id}")
            await crud.publish_to_custom_room(room_id,{
                    "type": "screen_share_started",
                    "user_id": user_id,
                    "message": "상대방이 화면 공유를 시작했습니다.",
                })
        elif message_type == "renegotiate_screen_share":
            await crud.publish_to_custom_room(room_id,{
                    "type": "renegotiate_screen_share",
                    "user_id": user_id,
                    "message": "상대방이 화면 공유 재협상을 요청했습니다.",
                })

        elif message_type == "match_result":
            reason = data.get("reason")
            if reason == "surrender":
                winner_id = opponent.user_id
            elif reason == "finish":
                winner_id = current_user.user_id
            else:
                winner_id = None
            await crud.process_custom_result(room_id, winner_id, reason)

        else:
            logger.warning(f"Unknown message type received in custom match {room_id}: {message_type}")
            await websocket.send_json({"type": "error", "message": "Unknown message type"})

    except Exception as e:
        logger.error(f"Error handling message in custom match {room_id} : {e}")
        await websocket.send_json({"type": "error", "message": str(e)})






async def define_users(room_id: int, user_id: int) -> Tuple[UserState, UserState | None]:
    updated_room = await crud.get_room_info(room_id)
    if updated_room.maker.user_id == user_id:
        return updated_room.maker, updated_room.user      # user 가 없으면 None
    else:
        return updated_room.user, updated_room.maker


