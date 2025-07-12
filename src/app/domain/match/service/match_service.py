from src.app.domain.game.service.problem_selector import select_problem_for_tiers
from src.app.domain.match.utils.queues import hard_queue, normal_queue, queue_lock
from src.app.domain.match.utils.matcher import hybrid_match, hard_match, force_match
from datetime import datetime, timezone
import asyncio
from sqlalchemy.orm import Session
from src.app.core.database import get_db  # DB 세션을 가져오기 위한 import 추가
from src.app.domain.match.crud import match_crud
from src.app.domain.user.crud.user_crud import get_user_mmr, get_user_by_id
from src.app.models.models import Match, Problem
from src.app.utils.tier_util import mmr_to_tier, refresh_tier_cnt
from src.app.utils.ws_manager import ws_manager
from src.app.domain.match.schemas.match_schemas import MatchLogSchema
from src.app.domain.game.crud.game_crud import get_problem_by_id
from src.app.utils.logging import logger
from itertools import count

# 매칭 루프 타이머
MATCH_INTERVAL = 1  # 초 세팅 0.5 = 500ms
GO_TO_HARD = 10  # 강제 풀 배치 기준 180 = 180s
match_id_counter = count(1)


class MatchService:
    def __init__(self):
        self._interval = MATCH_INTERVAL
        self._task: asyncio.Task | None = None

    async def _run(self):
        logger.info("Match service _run loop started.")
        #티어 카운트 최신화
        with next(get_db()) as db:
            await refresh_tier_cnt(db)
            logger.info("Tier dic func successed")
        while True:
            await asyncio.sleep(self._interval)
            # 백그라운드 태스크에서 DB 세션 사용을 위해 수동으로 세션 생성 및 전달
            with next(get_db()) as db:
                await self._tick(db)

    @staticmethod
    async def _tick(db: Session):  # DB 세션을 인자로 받도록 수정
        async with queue_lock:
            users = list(normal_queue) + list(hard_queue)
            if len(users) < 2:
                return

            (pairs, pre_waiting), algo = hybrid_match(users)
            logger.info(f"Matching algorithm used: {algo}. Found {len(pairs)} pairs.")

            normal_queue.clear()
            hard_queue.clear()

            hard_list = []
            waiting = []
            now = datetime.now(timezone.utc)
            for user in pre_waiting:
                if (now - user.joined_at).total_seconds() >= GO_TO_HARD:
                    hard_list.append(user)
                else:
                    waiting.append(user)
            logger.debug(f"Pre-waiting users: {len(pre_waiting)}, Hard list: {len(hard_list)}, Waiting: {len(waiting)}")

            # 강제 풀 매칭
            if len(hard_list) > 0:
                logger.info(f"Attempting forced matching for {len(hard_list)} users in hard list.")
                # 강제 그리디 1차 (hard 끼리)
                if len(hard_list) > 1:
                    hard_pairs, hard_waiter = hard_match(hard_list)
                    pairs.extend(hard_pairs)
                    hard_list = []
                    if hard_waiter:
                        hard_list.append(hard_waiter)
                    logger.info(f"Forced matching (hard-hard) found {len(hard_pairs)} pairs.")

                # 강제 그리디 2차 (그냥 가까운 놈 납치)
                if len(hard_list) == 1:
                    if len(waiting) > 0:
                        victim = force_match(hard_list[0], waiting)
                        pairs.append((hard_list[0], victim))
                        waiting.remove(victim)
                        logger.info(f"Forced matching (hard-normal) found a pair with victim {victim.id}.")
                    else:
                        hard_queue.append(hard_list[0])
                        logger.info(f"User {hard_list[0].id} re-added to hard queue as no victim found.")
            normal_queue.extend(waiting)
        # 매칭 성공 쌍에게 매칭 완료 함수 시행 (DB 세션 전달)
        await dispatch_pairs(db, pairs, algo)

    def start(self):
        logger.info("Starting match service.")
        if self._task is None:
            self._task = asyncio.create_task(self._run())
            logger.info("Match service task created.")

    async def stop(self):
        logger.info("Stopping match service.")
        if self._task:
            self._task.cancel()
            try:
                await self._task
                logger.info("Match service task cancelled successfully.")
            except asyncio.CancelledError:
                logger.warning("Match service task was already cancelled.")
                pass


# 매칭된 사용자 쌍에게 매칭 완료 메시지 전송
async def dispatch_pairs(db: Session, pairs, algo):
    """
    pairs: List[Tuple[MatchingUserInfo, MatchingUserInfo]]
    """
    logger.info(f"Dispatching {len(pairs)} matched pairs.")
    for u1, u2 in pairs:
        match_id = next(match_id_counter)
        logger.info(f"Generated new match ID: {match_id} for users {u1.id} and {u2.id}.")

        ws_manager.match_state[match_id] = {
            u1.id: False,
            u2.id: False,
        }

        # 각 사용자의 상세 정보 (닉네임, MMR) 조회
        user1_data = get_user_by_id(db, u1.id)
        user2_data = get_user_by_id(db, u2.id)

        user1_mmr = get_user_mmr(db, u1.id)
        user2_mmr = get_user_mmr(db, u2.id)

        # MMR을 기반으로 티어 계산
        user1_tier = mmr_to_tier(user1_mmr)
        user2_tier = mmr_to_tier(user2_mmr)

        # 각 사용자에게 전송할 상대방 정보 구성
        opponent1_info = {
            "id": user2_data.user_id,
            "nickname": user2_data.nickname,
            "tier": user2_tier,
        }
        opponent2_info = {
            "id": user1_data.user_id,
            "nickname": user1_data.nickname,
            "tier": user1_tier,
        }

        # u1에게 u2의 정보를 포함하여 매칭 완료 메시지 전송
        await ws_manager.broadcast(
            [u1.id],
            {
                "type": "match_found",
                "match_id": match_id,
                "opponent_ids": [u2.id],  # 상대방 ID만 전송
                "opponent_info": opponent1_info,  # 상대방 상세 정보 전송
                "time_limit": 20,
                "algo": algo,
            },
        )
        # u2에게 u1의 정보를 포함하여 매칭 완료 메시지 전송
        await ws_manager.broadcast(
            [u2.id],
            {
                "type": "match_found",
                "match_id": match_id,
                "opponent_ids": [u1.id],  # 상대방 ID만 전송
                "opponent_info": opponent2_info,  # 상대방 상세 정보 전송
                "time_limit": 20,
                "algo": algo,
            },
        )
        logger.info(f"Broadcasted match_found for match {match_id} to users {u1.id}, {u2.id}.")

        # 20초 타임아웃
        asyncio.create_task(handle_match_timeout(match_id, [u1.id, u2.id], 20))
        logger.info(f"Started match timeout task for match {match_id}.")


async def handle_match_timeout(match_id: int, users: list[int], timeout: int):
    logger.info(f"Match {match_id} timeout task started for {timeout} seconds.")
    await asyncio.sleep(timeout)
    if match_id in ws_manager.match_state and not all(ws_manager.match_state[match_id].values()):
        logger.warning(f"Match {match_id} timed out or was rejected. Broadcasting cancellation.")
        await ws_manager.broadcast(users, {"type": "match_cancelled", "reason": "timeout or rejection"})
        ws_manager.match_state.pop(match_id, None)
    else:
        logger.info(f"Match {match_id} was accepted before timeout.")


async def create_match_with_logs(db: Session, user_ids: list[int]) -> tuple[Match, Problem]:
    logger.info(f"Creating match with logs for users: {user_ids}")
    mmrs = [get_user_mmr(db, uid) for uid in user_ids]
    tiers = [mmr_to_tier(mmr) for mmr in mmrs]
    problem = await select_problem_for_tiers(db, tiers[0], tiers[1])  # 티어에 맞춰 랜덤 문제 반환
    logger.info(f"Selected problem {problem.problem_id} (difficulty: {problem.difficulty}) for match.")
    match = await match_crud.create_match(db, problem.problem_id)
    await match_crud.create_match_logs(db, match.match_id, user_ids, problem.problem_id)
    db.commit()
    logger.info(f"Match {match.match_id} created and logs saved for users {user_ids}.")
    return match, problem


async def get_match_logs_by_user_id(db: Session, user_id: int, counts: int):
    logger.info(f"Fetching {counts} match logs for user {user_id}.")
    logs_return_list = []

    logs = await match_crud.get_match_log_by_user_index(db, user_id, counts)
    if not logs:
        logger.info(f"No match logs found for user {user_id}.")
        return []

    for log in logs:
        problem_id = log.problem_id
        game = await get_problem_by_id(db, problem_id)
        result = log.result
        opponent_tier = mmr_to_tier(int(log.opponent_mmr))
        opponent = get_user_by_id(db, log.opponent_id)
        opponent_nick = opponent.nickname
        game_time = log.created_at
        difficultly = str(game.difficulty.value)
        earned = int(log.mmr_earned)
        title = str(game.title)
        result = MatchLogSchema(
            result=result,
            mmr_earned=earned,
            opponent_name=opponent_nick,
            opponent_tier=opponent_tier,
            game_difficulty=difficultly,
            game_time=game_time,
            game_title=title,
        )
        logs_return_list.append(result)
    logger.info(f"Successfully fetched {len(logs_return_list)} match logs for user {user_id}.")
    return logs_return_list


match_service = MatchService()
