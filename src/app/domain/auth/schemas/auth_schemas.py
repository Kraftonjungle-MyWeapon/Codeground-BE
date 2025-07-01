from typing import Optional
from pydantic import BaseModel, constr, EmailStr
from src.app.config.config import settings


# ✅ 회원가입 요청 스키마 (기존 UserSignupRequest → SignupRequest 로 이름 변경)
class SignupRequest(BaseModel):
    email: EmailStr
    username: str
    password: constr(min_length=8, max_length=20)
    nickname: str
    use_lang: str  # 예: Python, Java, C, C++
    tier_choice: str  # 예: 브론즈, 실버, 골드, 플래티넘 이상, 티어 없음


# ✅ 회원가입 응답 스키마 (기존 UserSignupResponse → SignupResponse 로 이름 변경)
class SignupResponse(BaseModel):
    email: str
    username: str
    nickname: str

    model_config = {"from_attributes": True}


# ✅ 토큰 응답
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


# ✅ 로그인 후 유저 정보 DTO (기존 UserDto → LoginUserDto 로 이름 변경)
class LoginUserDto(BaseModel):
    email: str
    username: str
    nickname: str

    model_config = {"from_attributes": True}
