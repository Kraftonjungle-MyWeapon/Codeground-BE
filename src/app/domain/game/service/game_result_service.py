from src.app.domain.match.utils.mmr_measure import full_update, MatchScore
from src.app.models.models import MatchResult, MatchFinishStatus, MatchStatus
from src.app.domain.match.crud.match_crud import (
    get_mmr_by_id,
    get_log_by_game_id,
)
from src.app.domain.ranking.crud.ranking_crud import (
    get_rank_by_id,
    get_users_in_mmr_range,
)
from src.app.domain.ranking.service.ranking_service import create_rank
from src.app.utils.tier_util import mmr_to_tier, tiers_cnt, tiers
from src.app.domain.achievement.service import achievement_service
from sqlalchemy.orm import Session
from src.app.models.models import Match
from datetime import datetime, timezone

RESULT_TO_SCORE = {
    MatchResult.WIN: MatchScore.WIN,
    MatchResult.DRAW: MatchScore.DRAW,
    MatchResult.LOSS: MatchScore.LOSS,
}


async def update_user_mmr(db: Session, game_id: int, user_id: int) -> None:
    user_mmr_info = await get_mmr_by_id(db, user_id)
    match_log = await get_log_by_game_id(db, game_id, user_id)

    user_rank = await get_rank_by_id(db, user_id)
    if not user_rank:
        await create_rank(db, user_id)
        user_rank = await get_rank_by_id(db, user_id)

    if None in (user_mmr_info, match_log):
        return

    ori_mmr = user_mmr_info.rating

    enemy_mmr = match_log.opponent_mmr
    enemy_rd = match_log.opponent_rd
    if isinstance(match_log.result, str):
        result_enum = MatchResult(match_log.result)
    else:
        result_enum = match_log.result

    score_enum = RESULT_TO_SCORE[result_enum]
    game = [(enemy_mmr, enemy_rd, score_enum)]

    new_rate, new_rd, new_sigma = full_update(
        user_mmr_info.rating,
        user_mmr_info.rating_devi,
        user_mmr_info.volatility,
        game,
    )

    user_mmr_info.rating = new_rate
    user_mmr_info.rating_devi = int(new_rd)
    user_mmr_info.volatility = new_sigma

    match_log.mmr_earned = new_rate - ori_mmr
    match_log.is_consumed = True
    user_rank.mmr = int(new_rate)

    user_tier = mmr_to_tier(int(user_mmr_info.rating))
    ori_tier = mmr_to_tier(int(ori_mmr))

    tiers_cnt[ori_tier] -= 1
    tiers_cnt[user_tier] += 1

    high_user_cnt = await get_high_tier_users(user_tier)

    # 랭크 최신화
    update_users = await get_users_in_mmr_range(
        db,
        min(ori_mmr, new_rate),
        max(ori_mmr, new_rate),
    )
    if len(update_users) <= 1:
        db.commit()
        return

    # 패배 시
    if ori_mmr > new_rate:
        ori_rank = user_rank.rank
        user_rank.rank = update_users[-1].rank
        user_rank.rank_diff = ori_rank - user_rank.rank

        start = ori_rank if user_rank.rank > high_user_cnt else high_user_cnt + 1
        for user in update_users:
            if user == user_rank or user.rank < ori_rank:
                continue
            user.rank = start
            user.rank_diff += 1
            start += 1

    # 승리 시
    else:
        ori_rank = user_rank.rank
        user_rank.rank = update_users[0].rank if update_users[0].rank > high_user_cnt else high_user_cnt + 1
        user_rank.rank_diff = ori_rank - user_rank.rank

        start = user_rank.rank + 1
        for user in update_users:
            if user == user_rank or user.rank > ori_rank:
                continue
            user.rank = start
            user.rank_diff -= 1
            start += 1

    db.commit()
    return


from src.app.models.models import AchievementTriggerType


async def update_user_log(
    db: Session,
    game_id: int,
    user_id: int,
    opponent_id: int,
    winner_id: int | None,
) -> None:
    # MatchLog 가져오기
    user_log = await get_log_by_game_id(db, game_id, user_id)
    opponent_log = await get_log_by_game_id(db, game_id, opponent_id)
    # 결과 기록
    if not winner_id:
        user_log.result = MatchResult.DRAW
        opponent_log.result = MatchResult.DRAW

    elif winner_id == user_id:
        user_log.result = MatchResult.WIN
        opponent_log.result = MatchResult.LOSS

    else:
        user_log.result = MatchResult.LOSS
        opponent_log.result = MatchResult.WIN

    db.commit()
    db.refresh(user_log)
    db.refresh(opponent_log)

    await update_user_mmr(db, game_id, user_id)
    await update_user_mmr(db, game_id, opponent_id)

    # 업적 확인 로직
    # 1. 게임 결과에 따른 업적 처리
    user_ids = [user_id, opponent_id]
    for u_id in user_ids:
        await achievement_service.handle_achievement_event(db, u_id, AchievementTriggerType.TOTAL_WIN)
        await achievement_service.handle_achievement_event(db, u_id, AchievementTriggerType.TOTAL_LOSS)
        await achievement_service.handle_achievement_event(db, u_id, AchievementTriggerType.TOTAL_DRAW)
        await achievement_service.handle_achievement_event(db, u_id, AchievementTriggerType.CONSECUTIVE_WIN)
        await achievement_service.handle_achievement_event(db, u_id, AchievementTriggerType.CONSECUTIVE_LOSS)

    # 2. 푼 문제 수, N번 안에 풀기, 오답 없이 승리 업적 처리 (승자에게만)
    if user_log.result == MatchResult.WIN:
        await achievement_service.handle_achievement_event(db, user_id, AchievementTriggerType.PROBLEM_SOLVED)
        await achievement_service.handle_achievement_event(
            db, user_id, AchievementTriggerType.WIN_WITHIN_N_SUBMISSIONS, submission_count=user_log.submission_count
        )
        await achievement_service.handle_achievement_event(
            db,
            user_id,
            AchievementTriggerType.FIRST_WIN,
        )
        await achievement_service.handle_achievement_event(
            db, user_id, AchievementTriggerType.WIN_WITHOUT_MISS, submission_count=user_log.submission_count
        )
    elif opponent_log.result == MatchResult.WIN:
        await achievement_service.handle_achievement_event(db, opponent_id, AchievementTriggerType.PROBLEM_SOLVED)
        await achievement_service.handle_achievement_event(
            db,
            opponent_id,
            AchievementTriggerType.WIN_WITHIN_N_SUBMISSIONS,
            submission_count=opponent_log.submission_count,
        )
        await achievement_service.handle_achievement_event(
            db,
            opponent_id,
            AchievementTriggerType.FIRST_WIN,
        )
        await achievement_service.handle_achievement_event(
            db, opponent_id, AchievementTriggerType.WIN_WITHOUT_MISS, submission_count=opponent_log.submission_count
        )

    # 3. 빨리 풀기 업적 처리 (승자에게만)
    if user_log.result == MatchResult.WIN:
        await achievement_service.handle_achievement_event(
            db, user_id, AchievementTriggerType.FAST_WIN, match_id=game_id
        )
    elif opponent_log.result == MatchResult.WIN:
        await achievement_service.handle_achievement_event(
            db, opponent_id, AchievementTriggerType.FAST_WIN, match_id=game_id
        )

    return


async def update_match(db: Session, match_id: int, reason: str) -> None:
    now = datetime.now(timezone.utc)
    match = db.query(Match).filter(Match.match_id == match_id).first()

    match.matching_status = MatchStatus.FINISH
    match.ending_status = MatchFinishStatus(reason)
    match.updated_at = now
    match.finished_at = now
    db.commit()


async def search_result(db: Session, game_id: int, user_id: int) -> str | None:
    match_log = await get_log_by_game_id(db, game_id, user_id)
    if not match_log or not match_log.result:
        return None
    return match_log.result.value


async def get_mmr_earned(db: Session, game_id: int, user_id: int) -> int:
    match_log = await get_log_by_game_id(db, game_id, user_id)
    return int(match_log.mmr_earned)


async def get_high_tier_users(user_tier: str) -> int:
    users_cnt = 0
    tiers_length = len(tiers) - 1
    for i in range(tiers_length):
        if user_tier == tiers[tiers_length - i]:
            break
        users_cnt += tiers_cnt[tiers[tiers_length - i]]
    return users_cnt
