from typing import Annotated
from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from src.app.core.database import get_db
from src.app.core.token import create_access_token
from src.app.domain.auth.service.github_service import get_github_auth_url, handle_github_callback
from src.app.config.config import settings
from src.app.domain.auth.router.auth_controller import get_cookie_options

router = APIRouter(prefix="/auth/github")

DB = Annotated[Session, Depends(get_db)]


@router.get("/login")  # ✅ 이렇게 수정
async def github_login():
    redirect_url = get_github_auth_url()
    return RedirectResponse(url=redirect_url, status_code=302)


@router.get("/callback")
async def github_callback(code: str, db: DB):
    result = await handle_github_callback(code, db)

    # 👉 이메일 중복 등으로 RedirectResponse가 반환된 경우
    if isinstance(result, RedirectResponse):
        return result

    user, is_new_user = result
    access_token = create_access_token(subject=user.email)

    redirect_url = f"{settings.FRONTEND_REDIRECT_URL}?new_user={str(is_new_user).lower()}"
    response = RedirectResponse(url=redirect_url, status_code=302)

    secure, samesite, domain, http_only = get_cookie_options()
    print("🍪 쿠키 옵션:", secure, samesite, domain, http_only)

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=http_only,
        secure=secure,
        samesite=samesite,
        path="/",
        max_age=60 * 60 * 24,
        domain=domain,
    )

    return response
