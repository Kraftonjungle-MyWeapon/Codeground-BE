from typing import Any, List
from sqlalchemy.orm import Session, InstrumentedAttribute
from sqlalchemy import desc, distinct
from src.app.models.models import RankChangeLog, Ranking


# 랭킹 테이블에 존재하는 모든 언어 목록 조회
def get_all_languages(db: Session) -> list[str]:
    result = db.query(distinct(Ranking.language)).all()
    return [lang for (lang,) in result]


# 특정 언어에 대해 MMR 기준 내림차순 정렬된 유저 랭킹 목록 조회
def get_users_by_language(db: Session, language: str) -> List[Any]:
    return db.query(Ranking).filter(Ranking.language == language).order_by(desc(Ranking.mmr)).all()


# 해당 유저의 순위 및 순위 차이 갱신
def update_user_rank(db: Session, ranking_id: int, new_rank: int, rank_diff: int):
    db.query(Ranking).filter(Ranking.ranking_id == ranking_id).update(
        {
            Ranking.rank: new_rank,
            Ranking.rank_diff: rank_diff,
        }
    )


# 순위 변화 기록 삽입
def insert_rank_change_log(
    db: Session,
    user_id: int,
    old_rank: int,
    new_rank: int,
    change_value: str,
):
    log = RankChangeLog(
        user_id=user_id,
        old_rank=old_rank,
        new_rank=new_rank,
        change_value=change_value,
    )
    db.add(log)


async def get_rank_by_id(db: Session, user_id: int) -> type[Ranking] | None:
    return db.query(Ranking).filter(Ranking.user_id == user_id).first()


async def get_all_users_mmr(db: Session) -> list[InstrumentedAttribute]:
    return db.query(Ranking.mmr).all()


async def get_users_in_mmr_range(db: Session, min_mmr: float, max_mmr: float) -> list[type[Ranking]]:
    return (
        db.query(Ranking)
        .filter(Ranking.mmr.between(min_mmr, max_mmr))
        .order_by(Ranking.mmr.desc(), Ranking.rank.asc())
        .all()
    )
