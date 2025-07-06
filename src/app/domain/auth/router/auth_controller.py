from typing import Annotated
import traceback
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, Response

from src.app.config.config import settings
from src.app.core.database import get_db
from src.app.domain.auth.schemas import auth_schemas as schemas
from src.app.domain.auth.service import auth_service as service
from src.app.core.token import create_access_token
from src.app.domain.auth.crud import auth_crud as crud

router = APIRouter()

DB = Annotated[Session, Depends(get_db)]


def get_cookie_options():
    if settings.ENV == "local":
        # 개발환경: 크로스도메인 문제 없으므로 lax, secure X
        return False, "lax", None, False
    else:
        # 운영/배포환경: cross-site 인증, https 강제
        return True, "none", ".code-ground.com", True


@router.post("/sign-up")
async def sign_up(sign_up_request: schemas.SignupRequest, db: DB, response: Response):
    try:
        await service.check_duplicate_email(db, str(sign_up_request.email))
        await service.check_duplicate_nickname(db, sign_up_request.nickname)
        await service.join(db, sign_up_request)
        db.commit()

        access_token = create_access_token(subject=str(sign_up_request.email))

        # 환경에 따라 쿠키 옵션 분기 (가독성 및 실수 방지)
        secure, samesite, domain, http_only = get_cookie_options()
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=http_only,
            max_age=60 * 60 * 24,
            secure=secure,
            samesite=samesite,
            path="/",
            domain=domain,
        )

        return schemas.TokenResponse(access_token=access_token, token_type="bearer")

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        print("회원가입 중 에러 발생:", e)
        traceback.print_exc()
        raise


@router.post("/login")
async def login(
        db: DB,
        response: Response,
        form_data: OAuth2PasswordRequestForm = Depends(),
):
    try:
        user = await service.authenticate_user(db, form_data.username, form_data.password)
        access_token = create_access_token(subject=user.email)

        # 환경에 따라 쿠키 옵션 분기 (가독성 및 실수 방지)
        secure, samesite, domain, http_only = get_cookie_options()
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=http_only,
            max_age=60 * 60 * 24,
            secure=secure,
            samesite=samesite,
            path="/",
            domain=domain,
        )

        return {"access_token": access_token, "token_type": "bearer"}

    except HTTPException as e:
        raise e
    except Exception as e:
        print("로그인 에러:", repr(e))
        raise HTTPException(status_code=500, detail="서버 오류로 로그인에 실패했습니다.")


@router.post("/reset-password/request")
async def request_password_reset(email: str, db: DB):
    await service.send_reset_password_email(db, email)
    return {"message": "비밀번호 초기화 메일을 발송했습니다."}


@router.post("/reset-password/verify")
async def verify_reset_code(email: str, code: str, db: DB):
    await service.verify_reset_code(db, email, code)
    return {"message": "인증 성공"}


@router.post("/reset-password/complete")
async def complete_password_reset(email: str, code: str, new_password: str, db: DB):
    await service.reset_password(db, email, code, new_password)
    return {"message": "비밀번호가 성공적으로 변경되었습니다."}


@router.get("/find-id")
async def find_id(email: str, db: DB):
    user = crud.get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=404, detail="등록되지 않은 이메일입니다.")
    return {"username": user.username, "nickname": user.nickname}


@router.get("/check-email")
async def check_email(email: str, db: DB):
    await service.check_duplicate_email(db, email)
    return {"available": True}


@router.get("/check-nickname")
async def check_nickname(nickname: str, db: DB):
    await service.check_duplicate_nickname(db, nickname)
    return {"available": True}
