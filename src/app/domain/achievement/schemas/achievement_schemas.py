from pydantic import BaseModel
from datetime import datetime
from src.app.models.models import AchievementTriggerType, RewardType


class AchievementBase(BaseModel):
    achievement_id: int
    title: str
    description: str | None
    trigger_type: AchievementTriggerType
    parameter: int | None
    reward_type: RewardType
    reward_amount: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserAchievementResponse(BaseModel):
    user_achievement_id: int
    user_id: int
    achievement_id: int
    current_value: int
    is_reward_received: bool
    obtained_at: datetime | None
    created_at: datetime
    modified_at: datetime
    achievement: AchievementBase  # Nested Pydantic model for the related Achievement

    class Config:
        from_attributes = True


class UserAchievementUpdate(BaseModel):
    is_reward_received: bool


class AllAchievementsResponse(BaseModel):
    all_achievements: list[AchievementBase]
    user_achievements: list[UserAchievementResponse]
