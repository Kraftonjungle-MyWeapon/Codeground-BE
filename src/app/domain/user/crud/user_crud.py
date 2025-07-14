from sqlalchemy.orm import Session
from src.app.models.models import User, UserMmr
from typing import Optional


def get_user_by_id(db: Session, input_id: int) -> Optional[User]:
    return db.query(User).filter(User.user_id == input_id).first()


def get_user_by_nickname(db: Session, nickname: str) -> Optional[User]:
    return db.query(User).filter(User.nickname == nickname).first()


def update_user(db: Session, user: User):
    db.add(user)
    db.commit()
    db.refresh(user)
    print("✅ updated user.nickname:", user.nickname)  # 🔍 확인용
    return user


def delete_user(db: Session, user_id: int) -> bool:
    """Delete user and related MMR information."""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        return False

    db.query(UserMmr).filter(UserMmr.user_id == user_id).delete()
    db.delete(user)
    db.commit()
    return True


def get_user_mmr(db: Session, user_id: int) -> int:
    mmr_obj = db.query(UserMmr).filter(UserMmr.user_id == user_id).first()
    return mmr_obj.rating if mmr_obj else 1000
