from fastapi import Depends, WebSocket, WebSocketDisconnect, APIRouter, Query
from src.app.domain.match.crud.match_crud import get_log_by_game_id
from src.app.utils.game_session import (
    game_rooms,
    game_user_map,
    ready_status,
    disconnected_users,
    end_times,
    is_paused,
    remaining_time_on_pause,
    timer_tasks,
)
import json
import asyncio
import time
from src.app.domain.game.service.game_result_service import update_user_log, update_match, get_mmr_earned
from typing import Annotated
from sqlalchemy.orm import Session
from src.app.core.database import get_db
from pathlib import Path
from src.app.utils.logging import logger

router = APIRouter()
DB = Annotated[Session, Depends(get_db)]

# 새로고침 등으로 인한 일시적 끊김 후 재접속을 기다리는 시간 (초)
RECONNECT_TIMEOUT = 5

DEFAULT_GAME_DURATION = 30 * 60  # 30분


def get_time_left(game_id: int) -> int:
    if is_paused.get(game_id):
        return int(remaining_time_on_pause.get(game_id, 0))
    end = end_times.get(game_id)
    if end is None:
        return 0
    return max(int(end - time.time()), 0)


async def start_game_timer(game_id: int, duration: int = DEFAULT_GAME_DURATION):
    end_times[game_id] = time.time() + duration
    is_paused[game_id] = False
    remaining_time_on_pause.pop(game_id, None)
    task = timer_tasks.get(game_id)
    if task:
        task.cancel()
    timer_tasks[game_id] = asyncio.create_task(periodic_timer_sync(game_id))
    await broadcast_to_room(game_id, {"type": "timer_sync", "timeLeft": get_time_left(game_id)})


def pause_game_timer(game_id: int):
    if not is_paused.get(game_id):
        remaining_time_on_pause[game_id] = get_time_left(game_id)
        is_paused[game_id] = True
        task = timer_tasks.pop(game_id, None)
        if task:
            task.cancel()


async def resume_game_timer(game_id: int):
    if is_paused.get(game_id):
        end_times[game_id] = time.time() + remaining_time_on_pause.get(game_id, 0)
        is_paused[game_id] = False
        await broadcast_to_room(game_id, {"type": "timer_sync", "timeLeft": get_time_left(game_id)})
        remaining_time_on_pause.pop(game_id, None)
        timer_tasks[game_id] = asyncio.create_task(periodic_timer_sync(game_id))


async def periodic_timer_sync(game_id: int, interval: int = 5):
    try:
        while True:
            await asyncio.sleep(interval)
            if is_paused.get(game_id):
                continue
            time_left = get_time_left(game_id)
            await broadcast_to_room(game_id, {"type": "timer_sync", "timeLeft": time_left})
            if time_left <= 0:
                break
    except asyncio.CancelledError:
        pass


@router.websocket("/ws/game/{game_id}")
async def game_websocket(db: DB, websocket: WebSocket, game_id: int, user_id: int = Query(...)):
    game_id = int(game_id)
    user_id = int(user_id)
    logger.info(f"User {user_id} attempting to connect to game {game_id}")

    try:
        # handshake는 서버가 먼저 accept 하지 않으면 작동하지 않음
        await websocket.accept()
    except RuntimeError as e:
        print(f"[WebSocket] accept() 실패: {e}")
        return

    # 인증: 해당 게임방에 참여할 자격이 있는지 확인
    if game_id not in game_user_map or user_id not in game_user_map[game_id]:
        logger.warning(f"Unauthorized connection attempt by user {user_id} to game {game_id}")
        await websocket.accept()  # 반드시 먼저 accept
        await websocket.close(code=4001)
        return

    # 재연결 감지 및 알림
    if disconnected_users.get(game_id) == user_id:
        disconnected_users.pop(game_id, None)
        logger.info(f"User {user_id} reconnected to game {game_id}")
        await broadcast_to_room(
            game_id,
            {
                "type": "opponent_rejoined",
                "user_id": user_id,
                "game_id": game_id,
                "message": "상대방이 다시 연결되었습니다.",
            },
            exclude=websocket,
        )
        await websocket.send_json({"type": "timer_sync", "timeLeft": get_time_left(game_id)})
    game_rooms[game_id].append(websocket)
    ready_status[game_id][user_id] = False
    logger.info(f"User {user_id} connected to game {game_id}")

    try:
        while True:
            # 클라이언트에서 받은 메시지를 처리 핸들러로 전달
            message = await websocket.receive_text()
            logger.debug(f"Received message from user {user_id} in game {game_id}: {message}")
            await handle_game_message(db, websocket, game_id, user_id, message)

    except WebSocketDisconnect:
        logger.info(f"User {user_id} disconnected from game {game_id}")
        # 연결 종료 시 정리
        if websocket in game_rooms[game_id]:
            game_rooms[game_id].remove(websocket)

        if user_id in ready_status.get(game_id, {}):
            ready_status[game_id].pop(user_id, None)

        # 상태 기록
        disconnected_users[game_id] = user_id

        async def delayed_leave():
            await asyncio.sleep(RECONNECT_TIMEOUT)
            # 아직 재접속되지 않았다면 ‘완전 이탈’ 처리
            if disconnected_users.get(game_id) == user_id:
                logger.info(f"User {user_id} permanently left game {game_id}")
                # 상대방에게 이탈 알림
                if game_rooms.get(game_id):
                    opponent_id = [uid for uid in game_user_map[game_id] if uid != user_id][0]
                    await process_match_result(db, game_id, user_id, opponent_id, "abandon")
                # 방 정리
                if not game_rooms.get(game_id):
                    logger.info(f"Closing game room {game_id}")
                    game_rooms.pop(game_id, None)
                    ready_status.pop(game_id, None)
                    disconnected_users.pop(game_id, None)
                    task = timer_tasks.pop(game_id, None)
                    if task:
                        task.cancel()
                    end_times.pop(game_id, None)
                    remaining_time_on_pause.pop(game_id, None)
                    is_paused.pop(game_id, None)

        # 백그라운드로 실행
        asyncio.create_task(delayed_leave())


async def handle_game_message(db, websocket: WebSocket, game_id: int, user_id: int, message: str):
    opponent_id = [uid for uid in game_user_map[game_id] if uid != user_id][0]
    try:
        data = json.loads(message)
        message_type = data.get("type")
        logger.info(f"Handling message type '{message_type}' for user {user_id} in game {game_id}")

        if message_type == "chat":
            # 채팅 메시지 전체 브로드캐스트
            await broadcast_to_room(game_id, {"type": "chat", "sender": user_id, "message": data.get("message")})

        elif message_type == "webrtc_signal":
            logger.debug(f"Broadcasting WebRTC signal from {user_id} in game {game_id}")
            # ICE candidate 혹은 SDP 교환
            await broadcast_to_room(
                game_id, {"type": "webrtc_signal", "sender": user_id, "signal": data.get("signal")}, exclude=websocket
            )

        elif message_type == "ready":
            ready_status[game_id][user_id] = True
            await broadcast_to_room(game_id, {"type": "player_ready", "user_id": user_id})
            logger.info(f"User {user_id} is ready in game {game_id}")
            if all(ready_status[game_id].values()):
                logger.info(f"All players are ready in game {game_id}")
                await broadcast_to_room(game_id, {"type": "all_ready"})
                await start_game_timer(game_id)

        elif message_type == "system_warning":
            await broadcast_to_room(
                game_id,
                {
                    "type": "system_warning",
                    "event": data.get("event"),
                    "count": data.get("count"),
                    "message": data.get("message"),
                    "user_id": user_id,  # 누가 보낸 건지 구분용
                },
            )

        elif message_type == "screen_share_stopped":
            logger.info(f"Screen share stopped by user {user_id} in game {game_id}")
            # 상대방에게 화면 공유 중단 알림 전송
            await broadcast_to_room(
                game_id,
                {
                    "type": "screen_share_stopped",
                    "user_id": user_id,
                    "message": "화면 공유가 중지되었습니다.",
                },
            )

        elif message_type == "screen_share_started":
            logger.info(f"Screen share started by user {user_id} in game {game_id}")
            await broadcast_to_room(
                game_id,
                {
                    "type": "screen_share_started",
                    "user_id": user_id,
                    "message": "상대방이 화면 공유를 시작했습니다.",
                },
            )

        elif message_type == "renegotiate_screen_share":
            # 화면 공유 재협상 요청 → 상대방에게 전달
            await broadcast_to_room(
                game_id,
                {
                    "type": "renegotiate_screen_share",
                    "user_id": user_id,
                    "message": "상대방이 화면 공유 재협상을 요청했습니다.",
                },
                exclude=websocket,
            )

        elif message_type == "pause_timer":
            pause_game_timer(game_id)
            await broadcast_to_room(game_id, {"type": "timer_paused"})

        elif message_type == "resume_timer":
            await resume_game_timer(game_id)

        # 제출 / 시간초과 / 항복 시 여기로
        # 각 reason 은 "finish" / "timeout" / "surrender"
        elif message_type == "match_result":
            reason = data.get("reason")
            await process_match_result(db, game_id, user_id, opponent_id, reason)

        else:
            logger.warning(f"Unknown message type received in game {game_id}: {message_type}")
            await websocket.send_json({"type": "error", "message": "Unknown message type"})

    except Exception as e:
        logger.error(f"Error handling message in game {game_id}: {e}")
        await websocket.send_json({"type": "error", "message": str(e)})


# 게임 내에서 발생하는 WebSocket 메시지를 처리하는 핵심 함수
async def broadcast_to_room(game_id: int, message: dict, exclude: WebSocket = None):
    disconnected_sockets = []

    for ws in game_rooms.get(game_id, [])[:]:  # 복사본으로 안전 순회
        if ws == exclude:
            continue
        try:
            await ws.send_json(message)
        except WebSocketDisconnect:
            disconnected_sockets.append(ws)
        except Exception as e:
            logger.error(f"[broadcast_to_room] Exception while sending to a websocket in game {game_id}: {e}")
            disconnected_sockets.append(ws)

    for ws in disconnected_sockets:
        if ws in game_rooms[game_id]:
            game_rooms[game_id].remove(ws)


async def process_match_result(db: Session, game_id: int, user_id: int, opponent_id: int, reason: str) -> None:
    # 정리: 타이머 종료
    task = timer_tasks.pop(game_id, None)
    if task:
        task.cancel()
    end_times.pop(game_id, None)
    remaining_time_on_pause.pop(game_id, None)
    is_paused.pop(game_id, None)

    # 동시 적용 시
    user_log = await get_log_by_game_id(db, game_id, user_id)
    if user_log.result:
        return None

    # 기권 시
    if reason in ("surrender", "abandon"):
        await update_match(db, game_id, "normal")
        await update_user_log(db, game_id, user_id, opponent_id, opponent_id)

        winner_id, reason = opponent_id, "surrender"
    # 시간 초과 시
    elif reason == "timeout":
        await update_match(db, game_id, "draw")
        await update_user_log(db, game_id, user_id, opponent_id, None)
        winner_id, reason = None, "draw"

    # 승리 시
    else:
        await update_match(db, game_id, "normal")
        await update_user_log(db, game_id, user_id, opponent_id, user_id)
        winner_id, reason = user_id, "finish"

    return await broadcast_result(db, game_id, user_id, opponent_id, winner_id, reason)


async def broadcast_result(
    db: Session, game_id: int, user_id: int, opponent_id: int, winner_id: int | None, reason: str | None
) -> None:
    if reason:
        user_earned = await get_mmr_earned(db, game_id, user_id)
        opponent_earned = await get_mmr_earned(db, game_id, opponent_id)
        await broadcast_to_room(
            game_id,
            {
                "type": "match_result",
                "winner": winner_id,
                "plus_mmr": max(user_earned, opponent_earned),
                "minus_mmr": min(user_earned, opponent_earned),
                "reason": reason,
            },
        )
    else:
        return


# 로컬용
tiers = ["bronze", "silver", "gold", "platinum", "diamond"]

ROOT_DIR = Path(__file__).resolve().parents[5]

# 2) data 폴더 절대경로
DATA_DIR = ROOT_DIR / "data"


@router.get("/for_local")
async def get_for_local():
    json_path = DATA_DIR / "cfb8fd36-1204-44cd-a91a-6f932427fbe1.json"  # C:\…\Codeground-Backend\data\prob-bronze.json
    with json_path.open(encoding="utf-8") as f:
        return json.load(f)
