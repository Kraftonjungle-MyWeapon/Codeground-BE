from sqlalchemy.orm import Session

from src.app.domain.match.crud.match_crud import get_mmr_by_id
from src.app.domain.ranking.crud import ranking_crud as crud
from src.app.domain.ranking.schemas import ranking_schemas as schemas
from src.app.domain.user.crud.user_crud import get_user_by_id
from src.app.models.models import UserMmr, Ranking
from src.app.utils.tier_util import mmr_to_tier, tiers_cnt, tiers


# 특정 언어 랭킹 리스트 조회
async def get_language_ranking(db: Session, language: str) -> schemas.RankingListResponse:
    raw_data = crud.get_users_by_language(db, language)

    rankings = [
        schemas.RankingEntry(
            user_id=ranking.user_id,
            nickname=ranking.user.nickname,
            mmr=ranking.mmr,
            rank=ranking.rank,
            rank_diff=ranking.rank_diff or 0,
        )
        for ranking in raw_data
    ]

    return schemas.RankingListResponse(language=language, rankings=rankings)


# 모든 언어별 랭킹 갱신 및 랭킹 변동 로그 기록
async def refresh_all_rankings(db: Session) -> dict:

    # 0) 먼저 ranking.mmr 을 user_mmr.rating 값으로 동기화
    #    (언어 구분 없이 전 사용자)
    all_mmr = db.query(UserMmr.user_id, UserMmr.rating).all()
    for user_id, rating in all_mmr:
        db.query(Ranking).filter(Ranking.user_id == user_id).update({Ranking.mmr: rating})
    languages = crud.get_all_languages(db)
    total_updated = 0
    total_logs = 0

    for lang in languages:
        rankings = crud.get_users_by_language(db, lang)

        for new_rank, ranking in enumerate(rankings, start=1):
            old_rank = ranking.rank or 0
            rank_diff = old_rank - new_rank  # 양수면 순위 상승

            # NEW / UP / DOWN / SAME 판정
            if old_rank == 0:
                diff_str = "NEW"
            elif rank_diff > 0:
                diff_str = "UP"
            elif rank_diff < 0:
                diff_str = "DOWN"
            else:
                diff_str = "SAME"

            # 모든 경우에 로그 남기기
            crud.insert_rank_change_log(
                db=db,
                user_id=ranking.user_id,
                old_rank=old_rank,
                new_rank=new_rank,
                change_value=diff_str,
            )
            total_logs += 1

            # 랭킹 테이블 업데이트
            crud.update_user_rank(
                db=db,
                ranking_id=ranking.ranking_id,
                new_rank=new_rank,
                rank_diff=rank_diff,
            )
            total_updated += 1

    db.commit()
    return {"updated": total_updated, "logs": total_logs}


async def create_rank(db: Session, user_id: int) -> None:
    user_info = get_user_by_id(db, user_id)
    user_mmr = await get_mmr_by_id(db, user_id)
    user_rank = Ranking(user_id=user_info.user_id, mmr=int(user_mmr.rating), language=user_info.use_lang, rank=0)
    user_tier = mmr_to_tier(int(user_mmr.rating))
    tiers_cnt[user_tier] += 1
    ranking = 0
    for tier in tiers:
        ranking += tiers_cnt[tier]
        if tier == user_tier:
            break
    user_rank.rank = ranking
    db.add(user_rank)
    db.commit()
    return
