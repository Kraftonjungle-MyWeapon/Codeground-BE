from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from src.app.core.database import get_db
from src.app.core.security import get_current_user
from src.app.domain.achievement.service import achievement_service
from src.app.models.models import User
from src.app.domain.achievement.schemas.achievement_schemas import UserAchievementResponse, AllAchievementsResponse

router = APIRouter()


@router.get("/users/{user_id}", response_model=List[UserAchievementResponse])
async def get_user_achievements_by_id(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    achievements = achievement_service.get_user_achievements(db, user_id)
    return achievements


@router.get("/users/{user_id}/all-achievements", response_model=AllAchievementsResponse)
async def get_all_and_user_achievements(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to view this user's achievements")

    data = achievement_service.get_all_and_user_achievements(db, user_id)
    return AllAchievementsResponse(
        all_achievements=data["all_achievements"],
        user_achievements=data["user_achievements"],
    )


@router.patch(
    "/users/{user_id}/achievements/{user_achievement_id}/reward-received",
    response_model=UserAchievementResponse,
)
async def update_user_achievement_reward_status(
    user_id: int,
    user_achievement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this user's achievements")
    try:
        updated_achievement = achievement_service.update_user_achievement_reward_status(
            db, user_id, user_achievement_id
        )
        return updated_achievement
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
