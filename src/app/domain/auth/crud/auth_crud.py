from sqlalchemy.orm import Session
from src.app.models.models import User, UserMmr, UserRole
from src.app.domain.auth.schemas import auth_schemas as schemas
from typing import Optional


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
        password=sign_up_request.password,  # 해시된 값
        use_lang=sign_up_request.use_lang,  # 사용언어 선택
    )
    db.add(new_user)
    # mmr db 반영 추가
    db.flush()
    db.refresh(new_user)

    mmr_row = UserMmr(user_id=new_user.user_id, rating=mmr)
    db.add(mmr_row)

    return new_user
