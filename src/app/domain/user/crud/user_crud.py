from sqlalchemy.orm import Session
from src.app.models.models import User, UserMmr
from typing import Optional


async def get_user_by_id(db: Session, input_id: int) -> Optional[User]:
    return db.query(User).filter(User.user_id == input_id).first()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def update_user(db: Session, user: User):
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_mmr(db: Session, user_id: int) -> int:
    mmr_obj = db.query(UserMmr).filter(UserMmr.user_id == user_id).first()
    return mmr_obj.rating if mmr_obj else 1000
