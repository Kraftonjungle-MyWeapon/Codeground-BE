from src.app.models.models import MatchLog
from typing import Optional, Sequence
from sqlalchemy.orm import Session
from src.app.models.models import Match, UserMmr, Problem
from sqlalchemy import select

LOGS_PER_CLICK = 15


async def get_mmr_by_id(db: Session, user_id: int) -> Optional[UserMmr]:  # User -> Optional[User]로 수정
    return db.query(UserMmr).filter(UserMmr.user_id == user_id).first()


async def get_log_by_id(db: Session, input_id: int) -> Optional[MatchLog]:
    return db.query(MatchLog).filter(MatchLog.user_id == input_id, MatchLog.is_consumed.is_(False)).first()


async def get_log_by_game_id(db: Session, match_id: int, input_id: int) -> Optional[MatchLog]:
    return db.query(MatchLog).filter(MatchLog.user_id == input_id, MatchLog.match_id == match_id).first()


async def create_match(db: Session, problem_id: int):
    match = Match(problem_id=problem_id, matching_status="created")
    db.add(match)
    db.flush()
    db.refresh(match)
    return match


async def create_match_logs(db: Session, match_id: int, user_ids: list[int], problem_id: int):
    user_a_mmr = await get_mmr_by_id(db, user_ids[0])
    user_b_mmr = await get_mmr_by_id(db, user_ids[1])
    print(user_ids[0], user_ids[1], user_a_mmr.user_id, user_b_mmr.user_id)
    user_a_log = MatchLog(
        match_id=match_id,
        problem_id=problem_id,
        user_id=user_ids[0],
        is_consumed=False,
        opponent_id=user_b_mmr.user_id,
        opponent_mmr=user_b_mmr.rating,
        opponent_rd=user_b_mmr.rating_devi,
    )

    user_b_log = MatchLog(
        match_id=match_id,
        problem_id=problem_id,
        user_id=user_ids[1],
        is_consumed=False,
        opponent_id=user_a_mmr.user_id,
        opponent_mmr=user_a_mmr.rating,
        opponent_rd=user_a_mmr.rating_devi,
    )

    db.add_all([user_a_log, user_b_log])
    print("after flush:", user_a_log.opponent_id, user_b_log.opponent_id)
    db.commit()
    return


async def get_match_log_by_user_index(db: Session, user_id: int, index: int) -> Sequence[MatchLog]:
    start = index * LOGS_PER_CLICK
    stmt = (
        select(MatchLog)
        .where(MatchLog.user_id == user_id)
        .order_by(MatchLog.created_at.desc())
        .offset(start)
        .limit(LOGS_PER_CLICK)
    )
    result = db.execute(stmt)
    return result.scalars().all()

def get_body_key_from_problem_id(db: Session, problem_id: int) -> str:
    # match_id로부터 body_key를 가져오는 함수
    # match 테이블에서 problem_id를 얻고, problem 테이블에서 body_key를 조회
    problem = db.query(Problem).filter(Problem.problem_id == problem_id).first()
    if problem is None:
        raise ValueError(f"No problem found with ID {problem_id}")
    return getattr(problem, "body_key")


def get_match_opponent_id(db: Session, match_id: int, reporter_user_id: int) -> Optional[int]:
    # 주어진 match_id에서 reporter_user_id의 상대방 ID를 찾습니다.
    match_log = db.query(MatchLog).filter(
        MatchLog.match_id == match_id,
        MatchLog.user_id == reporter_user_id
    ).first()
    if match_log:
        return match_log.opponent_id
    return None
