from src.app.domain.match.utils.mmr_measure import full_update, MatchScore
from src.app.models.models import MatchResult, MatchFinishStatus, MatchStatus
from src.app.domain.match.crud.match_crud import get_log_by_id, get_mmr_by_id, get_log_by_game_id
from src.app.domain.ranking.crud.ranking_crud import get_rank_by_id, get_users_in_mmr_range
from src.app.domain.ranking.service.ranking_service import create_rank
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
        user_mmr_info.rating, user_mmr_info.rating_devi, user_mmr_info.volatility, game
    )

    user_mmr_info.rating = new_rate
    user_mmr_info.rating_devi = int(new_rd)
    user_mmr_info.volatility = new_sigma

    match_log.mmr_earned = new_rate - ori_mmr
    match_log.is_consumed = True
    user_rank.mmr = int(new_rate)

    # update_users = await get_users_in_mmr_range(db,min(ori_mmr, new_rate), max(ori_mmr, new_rate))
    # if len(update_users) <= 1 :
    #     db.commit()
    #     return
    #
    # # 패배 시
    # if ori_mmr > new_rate:
    #     ori_rank = user_rank.rank
    #     user_rank.rank_diff = user_rank.rank - update_users[-1].rank
    #     user_rank.rank = update_users[-1].rank
    #     for user in update_users:
    #         if user == user_rank or user.rank < ori_rank:
    #             continue
    #         user.rank -= 1
    #         user.rank_diff += 1
    #
    # #승리 시
    # else:
    #     ori_rank = user_rank.rank
    #     user_rank.rank_diff = user_rank.rank - update_users[0].rank
    #     user_rank.rank = update_users[0].rank
    #
    #     for user in update_users:
    #         if user == user_rank or user.rank > ori_rank:
    #             continue
    #         user.rank += 1
    #         user.rank_diff -= 1

    db.commit()
    return


async def update_user_log(db: Session, game_id: int, user_id: int, result: str) -> None:
    # MatchLog 가져오기
    user_log = await get_log_by_game_id(db, game_id, user_id)

    # 결과 기록
    if result == "win":
        user_log.result = MatchResult.WIN

    elif result == "loss":
        user_log.result = MatchResult.LOSS

    elif result == "draw":
        user_log.result = MatchResult.DRAW

    else:
        raise ValueError(f"Invalid result '{result}' passed to update_user_log.")
    db.commit()
    db.refresh(user_log)

    return await update_user_mmr(db, game_id, user_id)


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
