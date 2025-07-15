import secrets
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.app.domain.auth.crud import auth_crud as crud
from src.app.domain.auth.schemas import auth_schemas as schemas
from src.app.core.password import get_password_hash, verify_password
from src.app.utils.email import send_email
from src.app.utils.logging import logger
from src.app.domain.achievement.service import achievement_service
from src.app.models.models import AchievementTriggerType

reset_code_store = {}


async def check_duplicate_email(db: Session, email: str) -> None:
    logger.info(f"Checking for duplicate email: {email}")
    if crud.get_by_email(db=db, email=email):
        logger.warning(f"Duplicate email found: {email}")
        raise HTTPException(detail="이미 사용 중인 이메일입니다.", status_code=status.HTTP_400_BAD_REQUEST)


async def check_duplicate_nickname(db: Session, nickname: str) -> None:
    logger.info(f"Checking for duplicate nickname: {nickname}")
    if crud.get_by_nickname(db, nickname):
        logger.warning(f"Duplicate nickname found: {nickname}")
        raise HTTPException(detail="이미 사용 중인 닉네임입니다.", status_code=status.HTTP_400_BAD_REQUEST)


async def join(db: Session, sign_up_request: schemas.SignupRequest) -> schemas.SignupResponse:
    logger.info(f"Joining user: {sign_up_request.email}")
    sign_up_request.password = get_password_hash(sign_up_request.password)
    # mmr = convert_choice_to_mmr(sign_up_request.tier_choice)
    mmr = 1000
    new_user = crud.join_user(db=db, sign_up_request=sign_up_request, use_lang=sign_up_request.use_lang, mmr=mmr)

    if not new_user:
        logger.error(f"Failed to sign up user: {sign_up_request.email}")
        raise HTTPException(detail="Fail Sign Up User", status_code=400)

    logger.info(f"User {sign_up_request.email} joined successfully")
    return schemas.SignupResponse.model_validate(new_user)


async def authenticate_user(db: Session, email: str, password: str) -> schemas.LoginUserDto:
    logger.info(f"Authenticating user: {email}")
    user = crud.get_user_by_email(db, email)

    if not user:
        logger.warning(f"Authentication failed for {email}: User not found")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다.",
        )

    # ✅ GitHub 로그인 계정이면 비밀번호가 없음
    if user.github_id and not user.password:
        logger.warning(f"Authentication failed for {email}: GitHub user attempted password login")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이 이메일은 GitHub 계정으로 가입되었습니다. GitHub 로그인으로 이용해주세요.",
        )

    if not await verify_password(password, user.password):
        logger.warning(f"Authentication failed for {email}: Invalid password")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다.",
        )

    

    # 로그인 정보 업데이트 및 업적 확인
    today = datetime.now(timezone.utc).date()
    last_login_date = user.last_login_at.date() if user.last_login_at else None

    if last_login_date == today:
        # 같은 날 재로그인 시 연속 로그인 유지
        pass
    elif last_login_date == today - timedelta(days=1):
        # 어제 로그인했으면 연속 로그인 증가
        user.consecutive_login_days += 1
    else:
        # 연속 로그인 끊김
        user.consecutive_login_days = 1

    user.last_login_at = datetime.now(timezone.utc)
    crud.update_user_login_info(db, user, user.last_login_at, user.consecutive_login_days)

    # 업적 확인
    await achievement_service.handle_achievement_event(
        db, user.user_id, AchievementTriggerType.CONSECUTIVE_LOGIN, current_value=user.consecutive_login_days
    )
    await achievement_service.handle_achievement_event(
        db,
        user.user_id,
        AchievementTriggerType.LOGIN_ON_DAY_OF_WEEK,
        current_value=datetime.now(timezone.utc).weekday(),  # 월요일=0, 일요일=6
    )

    logger.info(f"User {email} authenticated successfully")
    return schemas.LoginUserDto.model_validate(user)


def check_email_exists(db: Session, email: str) -> bool:
    logger.info(f"Checking if email exists: {email}")
    return crud.get_by_email(db, email) is not None


def check_nickname_exists(db: Session, nickname: str) -> bool:
    logger.info(f"Checking if nickname exists: {nickname}")
    return crud.get_by_nickname(db, nickname) is not None


async def send_reset_password_email(db: Session, email: str):
    logger.info(f"Sending password reset email to: {email}")
    user = crud.get_user_by_email(db, email)
    if not user:
        logger.warning(f"Password reset failed: User not found for email {email}")
        raise HTTPException(status_code=404, detail="등록되지 않은 이메일입니다.")

    code = secrets.token_hex(3)
    expires = datetime.now(timezone.utc) + timedelta(minutes=10)
    reset_code_store[email] = (code, expires)

    await send_email(to=email, subject="비밀번호 초기화", body=f"인증코드: {code}")
    logger.info(f"Password reset email sent to: {email}")


async def verify_reset_code(email: str, code: str):
    logger.info(f"Verifying password reset code for: {email}")
    stored = reset_code_store.get(email)
    if not stored:
        logger.warning(f"Password reset verification failed for {email}: No request found")
        raise HTTPException(status_code=400, detail="인증 요청이 없습니다.")
    if stored[0] != code:
        logger.warning(f"Password reset verification failed for {email}: Invalid code")
        raise HTTPException(status_code=400, detail="잘못된 인증 코드입니다.")
    if stored[1] < datetime.now(timezone.utc):
        logger.warning(f"Password reset verification failed for {email}: Code expired")
        raise HTTPException(status_code=400, detail="인증 코드가 만료되었습니다.")
    logger.info(f"Password reset code verified for: {email}")


async def reset_password(db: Session, email: str, code: str, new_password: str):
    logger.info(f"Resetting password for: {email}")
    await verify_reset_code(email, code)

    user = crud.get_user_by_email(db, email)
    if not user:
        logger.error(f"Password reset failed: User not found for email {email}")
        raise HTTPException(status_code=404, detail="유저 없음")

    user.password = get_password_hash(new_password)
    db.add(user)
    db.commit()
    reset_code_store.pop(email, None)
    logger.info(f"Password reset successfully for: {email}")
