from pydantic import BaseModel, EmailStr, HttpUrl, ConfigDict, model_validator
from typing import Optional
from datetime import datetime
from fastapi import HTTPException


# ✅ MMR 상세 표현용
class MyMmr(BaseModel):
    name: Optional[str] = None  # 티어 이름 (예: 브론즈, 실버)
    level: Optional[int] = None  # 단계 (로마자: I, II, III, IV, V)
    lp: Optional[int] = None  # LP 점수


# ✅ 사용자 정보 수정 요청
class UserUpdateRequest(BaseModel):
    current_password: Optional[str] = None  # 변경 전 비밀번호 확인용
    new_password: Optional[str] = None
    nickname: Optional[str] = None
    profile_img_url: Optional[HttpUrl] = None


# ✅ 최소 정보 반환용
class UserResponse(BaseModel):
    email: EmailStr


# ✅ 단순 사용자 정보 반환용
class UserResponseDto(BaseModel):
    user_id: int
    email: str
    username: str
    nickname: str
    use_lang: str

    model_config = {"from_attributes": True}


# ✅ 사용자 요청 DTO
class UserRequestDto(BaseModel):
    user_id: int
    email: str
    username: str
    nickname: str

    model_config = ConfigDict(from_attributes=True)


# ✅ MMR → 티어명 + 숫자레벨 + LP 변환
def parse_tier_from_mmr(mmr: int) -> tuple[str, int, int]:
    tiers = ["bronze", "silver", "gold", "platinum", "diamond", "challenger"]
    base_mmr = 1000
    lp = mmr % 100
    mmr_without_lp = mmr - lp
    gap = (mmr_without_lp - base_mmr) // 100  # 단계 수
    tier_index = gap // 5
    level_num = 5 - (gap % 5)  # 5~1

    if 0 <= tier_index < len(tiers) and 1 <= level_num <= 5:
        name = tiers[tier_index]
        level = level_num  # 숫자 그대로 반환
        return name, level, lp

    return "Unknown", 0, lp


# ✅ tier_choice 문자열("bronze 3", "silver 1", 등) → 시작 MMR로 변환
def convert_choice_to_mmr(tier_choice: str) -> int:
    tier_base = {
        "bronze": 1000,
        "silver": 1500,
        "gold": 2000,
    }

    # 예외 처리: 고정 티어
    if tier_choice == "platinum+":
        return 2500
    if tier_choice == "unranked":
        return 1000

    try:
        tier, level_str = tier_choice.lower().split()
        level = int(level_str)

        if tier not in tier_base:
            raise ValueError(f"Unknown tier: {tier}")
        if not 1 <= level <= 5:
            raise ValueError("Level must be between 1 and 5")

        base = tier_base[tier]
        mmr = base + (5 - level) * 100  # 역순
        return mmr

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid tier_choice: {e}")


# ✅ 전체 사용자 정보 반환용 (MMR 자동 가공 포함)
class UserDto(BaseModel):
    user_id: int
    email: str
    username: str
    nickname: str
    use_lang: str
    profile_img_url: Optional[HttpUrl] = None
    my_mmr: Optional[MyMmr] = None  # 변환된 형태로 제공

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    @model_validator(mode="before")
    def parse_mmr(cls, values: dict):
        raw_mmr = values.get("my_mmr")
        if isinstance(raw_mmr, int):
            name, level, lp = parse_tier_from_mmr(raw_mmr)
            values["my_mmr"] = MyMmr(name=name, level=level, lp=lp)
        return values


# ✅ 최근 경기 기록용
class MatchRecord(BaseModel):
    match_id: int
    result: str
    played_at: datetime


# ✅ 마이페이지에서 최근 경기 포함 응답
class UserResponseWithMatches(UserResponse):
    recent_matches: list[MatchRecord] = []


class UserUpdateResponse(BaseModel):
    message: str
    user: UserResponseDto

    model_config = ConfigDict(from_attributes=True)


class UserSignupRequest(BaseModel):
    email: EmailStr
    username: str
    password: str
    nickname: str
    use_lang: str  # Python, Java, C, C++
    tier_choice: str  # 브론즈, 실버, 골드, 플래티넘 이상, 티어 없음
