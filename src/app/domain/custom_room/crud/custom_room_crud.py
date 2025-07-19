import json
import redis.asyncio as aioredis
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from starlette.websockets import WebSocket, WebSocketDisconnect
from src.app.domain.user.crud.user_crud import get_user_by_id
from src.app.utils.game_session import custom_game_rooms, room_listenner_tasks, room_pubsubs
from src.app.config.config import settings
from src.app.domain.custom_room.schemas.custom_room_schema import CustomRoom, UserState, ResponseRoom
from src.app.domain.problem.crud.problem_crud import get_random_problem_for_custom
from src.app.models.models import Problem
from dataclasses import asdict
import asyncio
from sqlalchemy.orm import Session

rds = aioredis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT)
MAX_SLOT = 1000000 #1,000,000
ALLOWED_UPDATE_FIELDS = {"title", "category", "use_language", "difficulty"}

async def alloc_room_id() -> int:
    for slot in range(1,MAX_SLOT):
        if await rds.getbit("room_slots", slot) == 0:
            await rds.setbit("room_slots", slot, 1)
            return slot
    raise HTTPException(status_code=409, detail="No empty slots available.")

async def send_room_info(room: CustomRoom) -> None:
    # dataclass·SQLAlchemy·datetime 등 → 모두 JSON 가능 형태로 변환
    pubsub = rds.pubsub()
    room.maker.connected = True
    room.maker.ready = True
    room_dict = jsonable_encoder(room)
    room_json = json.dumps(room_dict, ensure_ascii=False)
    await rds.set(f"room:{room.room_id}", room_json)
    await rds.rpush("room_list", room.room_id)
    task = asyncio.create_task(pubsub_listener(room.room_id))
    room_listenner_tasks[room.room_id].append(task)

async def get_room_info(room_id: int) -> CustomRoom | None:
    data = await rds.get(f"room:{room_id}")
    if data is None:
        return None
    room_dict = json.loads(data)
    return dict_to_custom_room(room_dict)

async def join_to_room(db:Session,room_id: int, user_id: int) -> CustomRoom:
    data = await rds.get(f"room:{room_id}")
    if data is None:
        raise HTTPException(status_code=404, detail="No room found.")

    room_dict = json.loads(data)

    maker_dict = room_dict.get("maker")
    if maker_dict and maker_dict.get("user_id") == user_id:
        return dict_to_custom_room(room_dict)

    if room_dict.get("user") is not None:
        raise HTTPException(status_code=403, detail="Room already full.")

    new_user = await make_user_state(db, user_id)
    room_dict["user"] = asdict(new_user)
    await rds.set(f"room:{room_id}", json.dumps(room_dict))

    await info_updated(room_id, "player_join")

    return dict_to_custom_room(room_dict)

async def leave_from_room(room_id: int, user_id: int) -> None:
    sockets = custom_game_rooms.get(room_id, [])
    for ws in list(sockets):
        if getattr(ws, "user_id", None) == user_id:
            try:
                await ws.close()
            except WebSocketDisconnect:
                pass
            sockets.remove(ws)
            break

    data = await rds.get(f"room:{room_id}")
    if data is None:
        return

    room_dict = json.loads(data)
    maker = room_dict["maker"]

    if maker.get("user_id") == user_id:
        remain = room_dict.get("user")
        if remain is None:
            await delete_room(room_id)
            return

        remain["ready"] = True
        room_dict["maker"] = remain
        room_dict["user"] = None

        await rds.set(f"room:{room_id}", json.dumps(room_dict))

    else:
        room_dict["user"] = None
        await rds.set(f"room:{room_id}", json.dumps(room_dict))

async def delete_room(room_id: int) -> None:
    #방에 연결된 WebSocket 들을 미리 꺼내두기
    sockets = custom_game_rooms.get(room_id, [])

    for ws in list(sockets):
        try:
            await ws.close()
        except WebSocketDisconnect:
            pass

    custom_game_rooms.pop(room_id, None)

    tasks = room_listenner_tasks.pop(room_id, [])
    for task in tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    pubsub = rds.pubsub()
    await pubsub.unsubscribe(f"room:{room_id}")
    await rds.setbit("room_slots", room_id, 0)
    await rds.lrem("room_list", 0, str(room_id))
    await rds.delete(f"room:{room_id}")

    room_listenner_tasks.pop(room_id, None)

async def edit_room(room_id: int, user_id: int, update_info : dict) -> CustomRoom:
    room = await get_room_info(room_id)
    if room.maker.user_id != user_id:
        raise HTTPException(status_code=403, detail="User has not permission to edit this room.")

    for key, value in update_info.items():
        if key in ALLOWED_UPDATE_FIELDS and hasattr(room, key):
            setattr(room, key, value)
    room_dict = asdict(room)
    await rds.set(f"room:{room_id}", json.dumps(room_dict))
    await info_updated(room_id, "room_info_update")
    return room


async def get_rooms_by_list(page: int) -> list[ResponseRoom]:
    page_size = 20
    start = page * page_size
    end = start + page_size - 1

    room_ids = await rds.lrange("room_list", start, end)
    rooms = []
    for room_id in room_ids:
        data = await rds.get(f"room:{int(room_id)}")
        if data:
            data_info = dict_to_custom_room(json.loads(data))
            rooms.append(custom_room_to_response(data_info))
    return rooms

async def start_game(room_id: int) -> None:
    data = await rds.get(f"room:{room_id}")
    if data is None:
        raise HTTPException(status_code=404, detail="No room found.")

    room_dict = json.loads(data)
    if room_dict["user"] is None or room_dict["user"]["ready"] is False:
        raise HTTPException(status_code=403, detail="Need all user ready.")
    room_dict["is_gaming"] = True
    await rds.set(f"room:{room_id}", json.dumps(room_dict))
    return


async def end_game(room_id: int) -> None:
    data = await rds.get(f"room:{room_id}")
    if data is None:
        raise HTTPException(status_code=404, detail="No room found.")

    room_dict = json.loads(data)
    room_dict["is_gaming"] = False
    await rds.set(f"room:{room_id}", json.dumps(room_dict))
    return


async def ready_user(room_id: int, user_id : int) -> bool:
    room = await get_room_info(room_id)
    if not room.user or room.user.user_id != user_id:
        raise HTTPException(status_code=403, detail="User not found.")

    room.user.ready = not room.user.ready
    room_dict = asdict(room)
    await rds.set(f"room:{room.room_id}", json.dumps(room_dict))
    return room.user.ready

# async def unready_user(room_id: int, user_id: int):
#     room = await get_room_info(room_id)
#     if room.is_gaming:
#         raise HTTPException(status_code=403, detail="Game already started.")
#     if not room.user or room.user.user_id != user_id:
#         raise HTTPException(status_code=403, detail="User not found.")
#
#     room.user.ready = False
#     room_dict = asdict(room)
#     await rds.set(f"room:{room.room_id}", json.dumps(room_dict))
#     return

async def disconnect_user(room_id: int, user_id: int):
    return await change_connected(room_id, user_id, False)

async def connect_user(room_id: int, user_id: int):
    return await change_connected(room_id, user_id, True)

async def screen_share_stopped(room_id: int, user_id: int):
    return await change_screen_share(room_id, user_id, False)

async def screen_share_started(room_id: int, user_id: int):
    return await change_screen_share(room_id, user_id, True)

async def screen_share_ready(room_id: int, user_id: int):
    room = await get_room_info(room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    user = room.user if room.user.user_id == user_id else room.maker
    user.screen_sharing_ready = True
    room_dict = asdict(room)
    await rds.set(f"room:{room.room_id}", json.dumps(room_dict))


def dict_to_custom_room(room_dict: dict) -> CustomRoom:
    maker = UserState(**room_dict["maker"]) if room_dict.get("maker") else None
    user = UserState(**room_dict["user"]) if room_dict.get("user") else None
    return CustomRoom(
        room_id=room_dict["room_id"],
        maker=maker,
        user=user,
        difficulty=room_dict["difficulty"],
        category=room_dict["category"],
        use_language=room_dict["use_language"],
        title=room_dict["title"],
        is_gaming=room_dict["is_gaming"],
    )

def custom_room_to_response(data : CustomRoom) -> ResponseRoom:
    if not data.user:
        cnt = 1
    else:
        cnt = 2
    return ResponseRoom(
        room_id=data.room_id,
        maker=data.maker.nickname,
        user_cnt=cnt,
        category=data.category,
        difficulty=data.difficulty,
        use_language=data.use_language,
        title=data.title,
        is_gaming=data.is_gaming,
    )

async def change_connected(room_id: int, user_id: int, connected: bool):
    room = await get_room_info(room_id)

    if room.user and user_id == room.user.user_id:
        room.user.connected = connected

    elif room.maker and user_id == room.maker.user_id:
        room.maker.connected = connected
    else:
        raise HTTPException(status_code=403, detail="User not found.")

    room_dict = asdict(room)
    await rds.set(f"room:{room.room_id}", json.dumps(room_dict))
    return

async def change_screen_share(room_id: int, user_id: int, sharing: bool):
    room = await get_room_info(room_id)

    if room.user and user_id == room.user.user_id:
        room.user.screen_sharing = sharing
    elif room.maker and user_id == room.maker.user_id:
        room.maker.screen_sharing = sharing
    else:
        raise HTTPException(status_code=403, detail="User not found.")

    room_dict = asdict(room)
    await rds.set(f"room:{room.room_id}", json.dumps(room_dict))
    return

# 게임 내에서 발생하는 WebSocket 메시지를 처리하는 핵심 함수
async def publish_to_custom_room(room_id: int, message: dict):
    await rds.publish(f"room:{room_id}", json.dumps(message))

# 구독된 redis의 특정 id로부터 json을 받고 그걸 웹소캣으로 발송
async def pubsub_listener(room_id: int):
    pubsub = rds.pubsub()
    channel = f"room:{room_id}"
    await pubsub.subscribe(channel)

    # 인스턴스 추적
    room_pubsubs[room_id] = pubsub

    try:
        async for msg in pubsub.listen():
            if msg and msg["type"] == "message":
                raw = msg["data"]
                if isinstance(raw, bytes):
                    raw = raw.decode()
                data = json.loads(raw)

                disconnected = []
                for ws in set(custom_game_rooms.get(room_id, [])):
                    try:
                        await ws.send_json(data)
                    except WebSocketDisconnect:
                        disconnected.append(ws)

                for ws in disconnected:
                    custom_game_rooms[room_id].remove(ws)

                if not custom_game_rooms.get(room_id):
                    break

    finally:
        # loop 탈출 또는 예외 발생 시 클린업
        await pubsub.unsubscribe(channel)
        await pubsub.close()
        room_pubsubs.pop(room_id, None)

# 경기 결과 반환, 커스텀 매치라 점수 반영 X
# reason : surrender / abandon / finish / timeover
async def process_custom_result(room_id: int, winner_id: int | None, reason : str):
    room = await get_room_info(room_id)
    if not room.is_gaming:
        return

    room.is_gaming = False
    room_dict = asdict(room)
    await rds.set(f"room:{room_id}", json.dumps(room_dict))
    await publish_to_custom_room(
        room_id,
        {
            "type": "match_result",
            "room_id": room_id,
            "winner": winner_id,
            "reason": reason,
        }
    )


async def get_random_problem(db: Session,room_id: int) -> Problem:
    room = await get_room_info(room_id)
    problem = await get_random_problem_for_custom(db, room.category, room.difficulty)
    return problem

async def make_user_state(db : Session, user_id :int) -> UserState:
    user = get_user_by_id(db, user_id)
    if isinstance(user.mmr, (int, float)):
        mmr_val = int(user.mmr)
    else:
        mmr_val = int(getattr(user.mmr, "rating", 0))
    user_info = UserState(user_id=user_id, nickname=user.nickname, mmr=mmr_val, img_url=user.profile_img_url ,ready=False, screen_sharing=False, screen_sharing_ready= False, connected=False)
    return user_info

async def info_updated(room_id : int, msg : str):
    await publish_to_custom_room(room_id,{"type": msg})
