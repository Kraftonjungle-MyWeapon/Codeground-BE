import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.app.config.config import settings
from src.app.domain.auth.schemas import auth_schemas as schemas
from src.app.domain.auth.crud import auth_crud as crud
from fastapi.responses import RedirectResponse
from urllib.parse import urlencode


def get_github_auth_url() -> str:
    return (
        "https://github.com/login/oauth/authorize"
        f"?client_id={settings.GITHUB_CLIENT_ID}"
        "&scope=read:user user:email"
        f"&redirect_uri={settings.GITHUB_CALLBACK_URL}"
    )


async def handle_github_callback(code: str, db: Session):
    async with httpx.AsyncClient() as client:
        # 1. access token 요청
        token_response = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": settings.GITHUB_CALLBACK_URL,
            },
            headers={"Accept": "application/json"},
        )

        token_data = token_response.json()
        access_token = token_data.get("access_token")

        if not access_token:
            raise HTTPException(status_code=400, detail="GitHub access token 발급 실패")

        # 2. 유저 기본 정보 요청
        user_response = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"token {access_token}", "Accept": "application/json"},
        )
        github_user_data = user_response.json()
        github_id = str(github_user_data.get("id"))
        email = github_user_data.get("email")
        nickname = github_user_data.get("login")
        profile_img_url = github_user_data.get("avatar_url")

        # 3. 이메일이 없을 경우 보조 API로 조회
        if not email:
            user_emails_response = await client.get(
                "https://api.github.com/user/emails",
                headers={"Authorization": f"token {access_token}", "Accept": "application/json"},
            )

            if user_emails_response.status_code != 200:
                raise HTTPException(status_code=400, detail="GitHub 이메일 정보를 가져오지 못했습니다")

            emails_data = user_emails_response.json()
            if not isinstance(emails_data, list):
                raise HTTPException(status_code=400, detail="GitHub 이메일 응답 형식이 잘못되었습니다")

            primary_email = next((e for e in emails_data if isinstance(e, dict) and e.get("primary")), None)
            if primary_email:
                email = primary_email.get("email")

        if not email:
            raise HTTPException(status_code=400, detail="GitHub에서 이메일을 확인할 수 없습니다.")

        # ✅ 4. github_id 기준으로만 사용자 조회
        is_new_user = False
        user = crud.get_user_by_github_id(db, github_id)
        if user:
            return user, is_new_user

        # ✅ 5. 이메일 중복 계정이 있을 경우 오류 반환
        existing_user = crud.get_user_by_email(db, email)
        if existing_user:
            query_params = urlencode(
                {
                    "message": (
                        "이미 가입된 이메일로 등록된 계정이 있습니다. 일반 로그인 또는 다른 GitHub 계정을 사용해주세요."
                    )
                }
            )
            return RedirectResponse(
                url=f"{settings.FRONTEND_REDIRECT_URL.replace('/oauth/callback', '/login')}?{query_params}",
                status_code=302,
            )

        # 6. 신규 유저 생성
        is_new_user = True
        new_user_data = schemas.SocialSignupRequest(
            email=email,
            nickname=nickname,
            github_id=github_id,
            profile_img_url=profile_img_url,
            username=github_user_data.get("name") or nickname,
        )
        new_user = crud.create_social_user(db, new_user_data)
        return new_user, is_new_user
