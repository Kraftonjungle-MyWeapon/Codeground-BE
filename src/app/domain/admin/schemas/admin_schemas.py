from pydantic import BaseModel, Field, model_validator
from typing import Optional
from datetime import datetime
from src.app.models.models import AchievementTriggerType, RewardType


# 1. 유저 관리용 응답 스키마
class AdminUserOut(BaseModel):
    user_id: int
    email: str
    nickname: str
    is_banned: bool
    report_count: int
    created_at: datetime

    class Config:
        from_attributes = True


# 2. 신고(Report) 응답 스키마
class AdminReportOut(BaseModel):
    report_id: int
    reported_user_id: int
    reason: str
    description: Optional[str]
    is_approved: Optional[bool]
    created_at: datetime

    class Config:
        from_attributes = True


# 3. 문제(Problem) 응답 스키마
class AdminProblemOut(BaseModel):
    problem_id: int
    title: str
    difficulty: Optional[str]
    is_approved: Optional[bool]
    created_at: datetime

    class Config:
        from_attributes = True


# 4. 티어(또는 MMR) 분포 스키마
class TierDistributionItem(BaseModel):
    rating: float
    user_count: int

    class Config:
        from_attributes = True


# 5. 영구정지/해제 결과 등 단일 결과 응답
class AdminUserBanResult(BaseModel):
    user_id: int
    is_banned: bool


# 6. 신고 승인 결과
class AdminReportConfirmResult(BaseModel):
    report_id: int


# 7. 문제 승인 결과
class AdminProblemApproveResult(BaseModel):
    problem_id: int
    is_approved: bool


class AchievementBase(BaseModel):
    title: str = Field(..., description="업적 제목")
    description: str | None = Field(None, description="업적 설명")
    trigger_type: AchievementTriggerType = Field(..., description="업적 트리거 타입")
    parameter: int | None = Field(None, description="업적 달성 조건 값")
    reward_type: RewardType = Field(RewardType.BADGE, description="보상 타입")
    reward_amount: int = Field(1, description="보상 량")

    @classmethod
    def validate_enums(cls, values):
        if 'trigger_type' in values and isinstance(values['trigger_type'], str):
            values['trigger_type'] = AchievementTriggerType(values['trigger_type'])
        if 'reward_type' in values and isinstance(values['reward_type'], str):
            values['reward_type'] = RewardType(values['reward_type'])
        return values


class AchievementCreate(AchievementBase):
    pass


class AchievementUpdate(AchievementBase):
    pass


class AchievementResponse(AchievementBase):
    achievement_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
