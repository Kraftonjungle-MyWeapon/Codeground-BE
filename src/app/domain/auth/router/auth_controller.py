from typing import Annotated
import traceback
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from src.app.core.database import get_db
from src.app.domain.auth.schemas import auth_schemas as schemas
from src.app.domain.auth.service import auth_service as service
from src.app.core.token import create_access_token
from src.app.domain.auth.crud import auth_crud as crud
from fastapi import APIRouter, Depends, HTTPException, Response

router = APIRouter()

DB = Annotated[Session, Depends(get_db)]


@router.post("/sign-up")
def sign_up(sign_up_request: schemas.SignupRequest, db: DB):
    try:
        service.check_duplicate_email(db, str(sign_up_request.email))
        service.check_duplicate_nickname(db, sign_up_request.nickname)
        service.join(db, sign_up_request)
        db.commit()

        access_token = create_access_token(subject=str(sign_up_request.email))
        return schemas.TokenResponse(access_token=access_token)

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        print("회원가입 중 에러 발생:", e)
        traceback.print_exc()
        raise


@router.post("/login")
def login(
    db: DB,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    try:
        user = service.authenticate_user(db, form_data.username, form_data.password)
        access_token = create_access_token(subject=user.email)

        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,  # 보안을 위해 True 권장
            max_age=60 * 60 * 24,  # 24시간 (초 단위)
            secure=False,  # HTTPS 환경이면 True
            samesite="lax",
        )

        return {"message": "로그인 성공"}

    except HTTPException as e:
        raise e
    except Exception as e:
        print("로그인 에러:", repr(e))
        raise HTTPException(status_code=500, detail="서버 오류로 로그인에 실패했습니다.")


@router.get("/find-id")
def find_id(email: str, db: DB):
    user = crud.get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=404, detail="등록되지 않은 이메일입니다.")
    return {"username": user.username, "nickname": user.nickname}


@router.get("/check-email")
def check_email(email: str, db: DB):
    if service.check_email_exists(db, email):
        raise HTTPException(status_code=400, detail="이미 사용 중인 이메일입니다.")
    return {"available": True}


@router.get("/check-nickname")
def check_nickname(nickname: str, db: DB):
    if service.check_nickname_exists(db, nickname):
        raise HTTPException(status_code=400, detail="이미 사용 중인 닉네임입니다.")
    return {"available": True}


@router.post("/reset-password/request")
def request_password_reset(email: str, db: DB):
    service.send_reset_password_email(db, email)
    return {"message": "비밀번호 초기화 메일을 발송했습니다."}


@router.post("/reset-password/verify")
def verify_reset_code(email: str, code: str, db: DB):
    service.verify_reset_code(db, email, code)
    return {"message": "인증 성공"}


@router.post("/reset-password/complete")
def complete_password_reset(email: str, code: str, new_password: str, db: DB):
    service.reset_password(db, email, code, new_password)
    return {"message": "비밀번호가 성공적으로 변경되었습니다."}
