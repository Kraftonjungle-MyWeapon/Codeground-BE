import secrets

from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from src.app.domain.auth.crud import auth_crud as crud
from src.app.domain.auth.schemas import auth_schemas as schemas
from src.app.core.password import get_password_hash, verify_password
from src.app.models.models import User
from src.app.utils.email import send_email  # 메일 전송 유틸(비밀번호 초기화 시 필요)
from src.app.domain.user.schemas.user_schemas import convert_choice_to_mmr

reset_code_store = {}


def check_duplicate_email(db: Session, email: str) -> bool:
    if crud.get_by_email(db=db, email=email):
        raise HTTPException(detail="이미 사용 중인 이메일 입니다.", status_code=status.HTTP_400_BAD_REQUEST)
    return False


def check_duplicate_nickname(db: Session, nickname: str) -> bool:
    if db.query(User).filter(User.nickname == nickname).first():
        raise HTTPException(detail="이미 사용 중인 닉네임 입니다.", status_code=status.HTTP_400_BAD_REQUEST)
    return False


def join(db: Session, sign_up_request: schemas.SignupRequest) -> schemas.SignupResponse:
    sign_up_request.password = get_password_hash(sign_up_request.password)
    mmr = convert_choice_to_mmr(sign_up_request.tier_choice)
    new_user = crud.join_user(db=db, sign_up_request=sign_up_request, use_lang=sign_up_request.use_lang, mmr=mmr)

    if not new_user:
        raise HTTPException(detail="Fail Sign Up User", status_code=400)
    return schemas.SignupResponse.model_validate(new_user)


def authenticate_user(db: Session, email: str, password: str) -> schemas.LoginUserDto:
    user = crud.get_user_by_email(db, email)
    if not user or not verify_password(password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="이메일 또는 비밀번호가 올바르지 않습니다."
        )
    return schemas.LoginUserDto.model_validate(user)


def check_email_exists(db: Session, email: str) -> bool:
    return crud.get_by_email(db, email)


def check_nickname_exists(db: Session, nickname: str) -> bool:
    return crud.get_by_nickname(db, nickname)


def send_reset_password_email(db: Session, email: str):
    user = crud.get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=404, detail="등록되지 않은 이메일입니다.")
    code = secrets.token_hex(3)
    expires = datetime.now(timezone.utc) + timedelta(minutes=10)
    reset_code_store[email] = (code, expires)
    send_email(to=email, subject="비밀번호 초기화", body=f"인증코드: {code}")


def verify_reset_code(email: str, code: str):
    stored = reset_code_store.get(email)
    if not stored:
        raise HTTPException(status_code=400, detail="인증 요청이 없습니다.")
    if stored[0] != code:
        raise HTTPException(status_code=400, detail="잘못된 인증 코드입니다.")
    if stored[1] < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="인증 코드가 만료되었습니다.")


def reset_password(db: Session, email: str, code: str, new_password: str):
    verify_reset_code(email, code)
    user = crud.get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=404, detail="유저 없음")
    user.password = get_password_hash(new_password)
    db.add(user)
    db.commit()
    reset_code_store.pop(email, None)
