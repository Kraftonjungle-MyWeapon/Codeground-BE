from typing import Annotated
from sqlalchemy.orm import Session

from src.app.core.database import get_db
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from src.app.utils.ws_manager import ws_manager
from src.app.utils.game_session import game_user_map
from src.app.domain.match.utils.queues import enqueue_user, dequeue_user, queue_lock, user_cache, requeue_user
from src.app.domain.match.service import match_service as service
from src.app.domain.user.service.user_service import get_user_data
from src.app.models.models import Problem
from src.app.utils.s3_utils import issue_problem_urls
from src.app.domain.match.schemas import match_schemas as schemas

router = APIRouter()
DB = Annotated[Session, Depends(get_db)]


@router.websocket("/ws/match/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: int,
    db: DB,
):
    user_id = int(user_id)
    current_user = await get_user_data(db, user_id)
    # ── 2) 매칭 큐 등록 ────────────────────
    await enqueue_user(db, current_user)  # 반드시 await

    # ── 3) 웹소켓 등록 ─────────────────────
    await ws_manager.connect(user_id, websocket)

    try:

        while True:
            data = await websocket.receive_json()
            if data["type"] == "match_accept":
                await handle_accept(data["match_id"], user_id, db)
            elif data["type"] == "match_reject":
                await handle_match_reject(data["match_id"], user_id)
            elif data["type"] == "cancel_queue":
                await match_cancel(user_id)  # ← 큐에서 제거
                await websocket.send_json({"type": "queue_cancelled"})
    except WebSocketDisconnect:
        ws_manager.disconnect(user_id)
        await match_cancel(user_id)


async def handle_accept(match_id: int, user_id: int, db: Session):
    if match_id not in ws_manager.match_state:
        return

    ws_manager.match_state[match_id][user_id] = True

    other_users = [uid for uid, accepted in ws_manager.match_state[match_id].items() if uid != user_id and not accepted]
    if other_users:
        await ws_manager.broadcast(
            other_users,
            {"type": "opponent_accepted", "user_id": user_id, "match_id": match_id},
        )

    if all(ws_manager.match_state[match_id].values()):
        users = list(ws_manager.match_state[match_id].keys())

        match, problem = await service.create_match_with_logs(db, users)


        # 여기에서 게임방 유저 등록
        for uid in users:
            user_cache.pop(uid, None)
        game_user_map[match.match_id] = users

        print(f"[DEBUG] match_id: {match.match_id}, users: {users}, problem: {problem.problem_id}, difficulty: {problem.difficulty}")

        presigned = await issue_problem_urls(problem)

        msg = {
            "type": "match_accepted",
            "game_id": match.match_id,
            "join_url": f"/game/{match.match_id}",
            "problem": {
                "problem_id": problem.problem_id,
                "problem_url": presigned["problem_url"],
                "image_urls" : presigned["image_urls"],
                "difficulty": problem.difficulty,
            },
        }
        print("[DEBUG] ws_manager.broadcast(match_accepted):", msg)
        await ws_manager.broadcast(users, msg)

        ws_manager.match_state.pop(match_id, None)


async def handle_match_reject(match_id: int, rejecting_user: int):
    if match_id not in ws_manager.match_state:
        return

    users = list(ws_manager.match_state[match_id].keys())
    accepted_user_id = [uid for uid in users if uid != rejecting_user][0]  # 상대 유저 ID 추출
    # 상대 유저를 다시 큐에 넣기
    await requeue_user(accepted_user_id)

    # 거절 브로드캐스트 및 상태 제거
    await ws_manager.broadcast(users, {"type": "match_cancelled", "reason": "rejected", "rejected_by": rejecting_user})
    ws_manager.match_state.pop(match_id, None)


async def match_cancel(user_id: int):
    user_cache.pop(user_id, None)
    await queue_lock.acquire()
    try:
        await dequeue_user(user_id)

    finally:
        queue_lock.release()

    return {"ok": True}


@router.get("/match_logs/{user_id}/{count}", response_model=list[schemas.MatchLogSchema])
async def get_user_match_logs(db: DB, user_id: int, count : int):
    match_logs = await service.get_match_logs_by_user_id(db, user_id, count)
    print(match_logs)

    return match_logs

