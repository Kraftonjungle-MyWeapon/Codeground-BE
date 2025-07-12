from sqlalchemy.orm import Session
from sqlalchemy import func
from src.app.models.models import User, CheatReport, Problem, MatchLog, Match, Ranking, UserMmr

# 1. 유저 전체 목록 조회 (검색)
# nice to have -> 필터링 기능
def get_all_users(db: Session):
    return db.query(User).all()

# 2. 특정 유저 제재(e.g. ban 처리
def ban_user(db: Session, user_id: int):
    user = db.query(User).filter(User.user_id == user_id).first()
    if user:
        user.role = 'BANNED'  # 컬럼명/정책에 따라 다를 수 있음
        db.commit()
        db.refresh(user)
    return user