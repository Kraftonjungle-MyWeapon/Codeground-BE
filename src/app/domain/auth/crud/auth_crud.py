from sqlalchemy.orm import Session
from src.app.models.models import User, UserMmr, UserRole
from src.app.domain.auth.schemas import auth_schemas as schemas
from typing import Optional
from datetime import datetime


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()


def get_by_email(db: Session, email: str) -> bool:
    search_email = db.query(User).filter(User.email == email).first()
    return True if search_email else False


def get_by_nickname(db: Session, nickname: str) -> bool:
    return db.query(User).filter(User.nickname == nickname).first() is not None


def join_user(db: Session, sign_up_request: schemas.SignupRequest, mmr: int, use_lang: str) -> User:
    new_user = User(
        email=str(sign_up_request.email),
        username=sign_up_request.username,
        nickname=sign_up_request.nickname,
        role=UserRole.USER,
        password=sign_up_request.password,
        use_lang=sign_up_request.use_lang,
    )
    db.add(new_user)
    db.flush()
    db.refresh(new_user)

    mmr_row = UserMmr(user_id=new_user.user_id, rating=mmr)
    db.add(mmr_row)

    return new_user


def get_user_by_github_id(db: Session, github_id: str) -> Optional[User]:
    return db.query(User).filter(User.github_id == github_id).first()


def create_social_user(db: Session, user_data: schemas.SocialSignupRequest) -> User:
    new_user = User(
        email=str(user_data.email),
        username=user_data.username,
        nickname=user_data.nickname,
        role=UserRole.USER,
        github_id=user_data.github_id,
        profile_img_url=user_data.profile_img_url,
    )
    db.add(new_user)
    db.flush()

    mmr_row = UserMmr(user_id=new_user.user_id, rating=1000)
    db.add(mmr_row)
    db.commit()
    db.refresh(new_user)

    return new_user


def update_user_login_info(db: Session, user: User, last_login_at: datetime, consecutive_login_days: int) -> User:
    user.last_login_at = last_login_at
    user.consecutive_login_days = consecutive_login_days
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
