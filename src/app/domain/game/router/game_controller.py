from fastapi import Depends, WebSocket, WebSocketDisconnect, APIRouter, Query
from src.app.utils.game_session import game_rooms, game_user_map, ready_status, disconnected_users
import json
import asyncio
from src.app.domain.game.service.game_result_service import update_user_log, update_match, search_result, get_mmr_earned
from typing import Annotated
from sqlalchemy.orm import Session
from src.app.core.database import get_db
from pathlib import Path

router = APIRouter()
DB = Annotated[Session, Depends(get_db)]

# 새로고침 등으로 인한 일시적 끊김 후 재접속을 기다리는 시간 (초)
RECONNECT_TIMEOUT = 5


@router.websocket("/ws/game/{game_id}")
async def game_websocket(db: DB, websocket: WebSocket, game_id: int, user_id: int = Query(...)):
    game_id = int(game_id)
    user_id = int(user_id)

    await websocket.accept()

    # 인증: 해당 게임방에 참여할 자격이 있는지 확인
    if game_id not in game_user_map or user_id not in game_user_map[game_id]:
        await websocket.accept()  # 반드시 먼저 accept
        await websocket.close(code=4001)
        return

    # 재연결 감지 및 알림
    if disconnected_users.get(game_id) == user_id:
        disconnected_users.pop(game_id, None)
        await broadcast_to_room(
            game_id,
            {
                "type": "opponent_rejoined",
                "user_id": user_id,
                "game_id": game_id,
                "message": "상대방이 다시 연결되었습니다.",
            },
            exclude=websocket
        )
    game_rooms[game_id].append(websocket)
    ready_status[game_id][user_id] = False

    try:
        while True:
            # 클라이언트에서 받은 메시지를 처리 핸들러로 전달
            message = await websocket.receive_text()

            await handle_game_message(db, websocket, game_id, user_id, message)

    except WebSocketDisconnect:
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
                # 상대방에게 이탈 알림
                if game_rooms.get(game_id):
                    await broadcast_to_room(
                        game_id,
                        {
                            "type": "opponent_left",
                            "user_id": user_id,
                            "message": "상대방이 연결을 종료했습니다. 계속 문제를 푸시하시겠습니까?"
                        }
                    )
                # 방 정리
                if not game_rooms.get(game_id):
                    game_rooms.pop(game_id, None)
                    ready_status.pop(game_id, None)
                    disconnected_users.pop(game_id, None)

        # 백그라운드로 실행
        asyncio.create_task(delayed_leave())


async def handle_game_message(db, websocket: WebSocket, game_id: int, user_id: int, message: str):
    opponent_id = [uid for uid in game_user_map[game_id] if uid != user_id][0]
    try:
        data = json.loads(message)
        message_type = data.get("type")

        if message_type == "chat":
            # 채팅 메시지 전체 브로드캐스트
            await broadcast_to_room(game_id, {"type": "chat", "sender": user_id, "message": data.get("message")})

        elif message_type == "webrtc_signal":
            # ICE candidate 혹은 SDP 교환
            await broadcast_to_room(
                game_id, {"type": "webrtc_signal", "sender": user_id, "signal": data.get("signal")}, exclude=websocket
            )

        elif message_type == "ready":
            ready_status[game_id][user_id] = True
            await broadcast_to_room(game_id, {"type": "player_ready", "user_id": user_id})
            if all(ready_status[game_id].values()):
                await broadcast_to_room(game_id, {"type": "all_ready"})

        elif message_type == "system_warning":
            await broadcast_to_room(game_id, {
                "type": "system_warning",
                "event": data.get("event"),
                "count": data.get("count"),
                "message": data.get("message"),
                "user_id": user_id,  # 누가 보낸 건지 구분용
            })

        elif message_type == "screen_share_stopped":
            print("screen_share_stopped")
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
            await broadcast_to_room(
                game_id,
                {
                    "type": "screen_share_started",
                    "user_id": user_id,
                    "message": "상대방이 화면 공유를 시작했습니다.",
                },
            )

        # 제출 / 시간초과 / 항복 시 여기로
        # 각 reason 은 "finish" / "timeout" / "surrender"
        elif message_type == "match_result":
            reason = data.get("reason")
            print("시작")
            winner_id, reason = await process_match_result(db, game_id, user_id, opponent_id, reason)
            mmr_earned = await get_mmr_earned(db, game_id, user_id)
            print(winner_id, reason, mmr_earned)

            await broadcast_to_room(game_id, {
                "type": "match_result",
                "winner": winner_id,
                "earned": mmr_earned,
                "reason": reason
            })

        else:
            print("에러 1")
            await websocket.send_json({"type": "error", "message": "Unknown message type"})

    except Exception as e:
        print("에러 2")
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
            print(f"[broadcast_to_room] 전송 중 예외 발생: {e}")
            disconnected_sockets.append(ws)

    for ws in disconnected_sockets:
        if ws in game_rooms[game_id]:
            game_rooms[game_id].remove(ws)


async def process_match_result(
        db: Session, game_id: int, user_id: int, opponent_id: int, reason: str
) -> (int | None, str):
    opponent_result = await search_result(db, game_id, opponent_id)
    # 기권 시
    if reason in ("surrender", "abandon"):
        await update_user_log(db, game_id, user_id, "loss")
        if opponent_result and opponent_result == "loss":
            await update_match(db, game_id, "abnormal")
        # 패배
        return opponent_id, "surrender"
    # 시간 초과 시
    elif reason == "timeout":
        # 상대방 상태 판단
        if opponent_result == "loss":
            await update_user_log(db, game_id, user_id, "win")
            await update_match(db, game_id, "abnormal")
            # 상대 기권 시 부전승
            return user_id, "walkover"

        elif opponent_result == "win":
            await update_user_log(db, game_id, user_id, "loss")
            # 상대가 이미 제출 완료 시 패배
            return opponent_id, "late"

        else:
            # 상대 또한 timeout 일 시, 무승부
            await update_user_log(db, game_id, user_id, "draw")
            await update_match(db, game_id, "draw")
            return None, "draw"

    else:
        if opponent_result == "win":
            await update_user_log(db, game_id, user_id, "loss")
            return opponent_id, "late"
        else:
            await update_user_log(db, game_id, user_id, "win")
            await update_match(db, game_id, "normal")
            return user_id, "finish"


#로컬용
tiers = ['bronze', 'silver', 'gold', 'platinum', 'diamond']

ROOT_DIR = Path(__file__).resolve().parents[5]   # src → game → domain → app

# 2) data 폴더 절대경로
DATA_DIR = ROOT_DIR / "data"

@router.get("/for_local")
async def get_for_local():
    json_path = DATA_DIR / "prob-bronze.json"    # C:\\…\\Codeground-Backend\\data\\prob-bronze.json
    with json_path.open(encoding="utf-8") as f:
        return json.load(f)
