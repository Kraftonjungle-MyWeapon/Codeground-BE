from datetime import datetime, timezone
from sqlalchemy.orm import Session

from src.app.domain.achievement.crud import achievement_crud
from src.app.models.models import Achievement, UserAchievement, AchievementTriggerType


async def check_and_unlock_achievements(
    db: Session,
    user_id: int,
    trigger_type: AchievementTriggerType,
    current_value: int,
) -> None:
    achievements: list[Achievement] = achievement_crud.get_achievements_by_type(
        db,
        trigger_type,
    )
    for ach in achievements:
        if ach.parameter is not None:
            # "적을수록 좋은" 업적 (예: N번 안에 풀기, 빨리 풀기, 오답 없이 승리)
            if trigger_type in [
                AchievementTriggerType.WIN_WITHIN_N_SUBMISSIONS,
                AchievementTriggerType.FAST_WIN,
                AchievementTriggerType.WIN_WITHOUT_MISS,
            ]:
                condition = current_value <= ach.parameter
            # "많을수록 좋은" 일반적인 업적 (예: 첫 승리)
            elif trigger_type == AchievementTriggerType.FIRST_WIN:
                condition = current_value >= 1  # 첫 승리는 parameter가 1 이상이면 달성
            elif trigger_type == AchievementTriggerType.LOGIN_ON_DAY_OF_WEEK:
                condition = current_value == ach.parameter  # 요일은 parameter와 정확히 일치해야 함
            else:
                condition = current_value >= ach.parameter

            if condition:
                existing = achievement_crud.get_user_achievement(
                    db,
                    user_id,
                    ach.achievement_id,
                )
                if not existing:
                    ua = achievement_crud.create_user_achievement(
                        db,
                        user_id,
                        ach.achievement_id,
                    )
                    ua.current_value = current_value
                    ua.obtained_at = datetime.now(timezone.utc)
    db.commit()


async def handle_achievement_event(
    db: Session,
    user_id: int,
    trigger_type: AchievementTriggerType,
    # N번 안에 풀기, 빨리 풀기 등 추가 파라미터가 필요한 경우를 대비
    **kwargs,
) -> None:
    current_value = 0
    if trigger_type == AchievementTriggerType.TOTAL_WIN:
        current_value = achievement_crud.get_total_wins(db, user_id)
    elif trigger_type == AchievementTriggerType.TOTAL_LOSS:
        current_value = achievement_crud.get_total_losses(db, user_id)
    elif trigger_type == AchievementTriggerType.TOTAL_DRAW:
        current_value = achievement_crud.get_total_draws(db, user_id)
    elif trigger_type == AchievementTriggerType.FIRST_WIN:
        current_value = achievement_crud.get_total_wins(db, user_id)
    elif trigger_type == AchievementTriggerType.CONSECUTIVE_WIN:
        current_value = achievement_crud.get_consecutive_wins(db, user_id)
    elif trigger_type == AchievementTriggerType.CONSECUTIVE_LOSS:
        current_value = achievement_crud.get_consecutive_losses(db, user_id)
    elif trigger_type == AchievementTriggerType.PROBLEM_SOLVED:
        current_value = achievement_crud.get_total_problems_solved(db, user_id)
    elif trigger_type == AchievementTriggerType.WIN_WITHIN_N_SUBMISSIONS:
        current_value = kwargs.get("submission_count", 0)
    elif trigger_type == AchievementTriggerType.WIN_WITHOUT_MISS:
        current_value = kwargs.get("submission_count", 0)
    elif trigger_type == AchievementTriggerType.APPROVED_PROBLEM_COUNT:
        current_value = achievement_crud.get_approved_problem_count(db, user_id)
    elif trigger_type == AchievementTriggerType.FAST_WIN:
        match_id = kwargs.get("match_id")
        if match_id:
            duration = achievement_crud.get_match_duration_seconds(db, match_id)
            if duration is not None:
                current_value = duration
    elif trigger_type == AchievementTriggerType.CONSECUTIVE_LOGIN:
        current_value = kwargs.get("current_value", 0)
    elif trigger_type == AchievementTriggerType.LOGIN_ON_DAY_OF_WEEK:
        current_value = kwargs.get("current_value", 0)

    if current_value > 0 or trigger_type == AchievementTriggerType.LOGIN_ON_DAY_OF_WEEK:
        await check_and_unlock_achievements(
            db,
            user_id,
            trigger_type,
            current_value,
        )


def get_user_achievements(db: Session, user_id: int) -> list[UserAchievement]:
    return achievement_crud.list_user_achievements(db, user_id)


def update_user_achievement_reward_status(
    db: Session,
    user_id: int,
    user_achievement_id: int,
) -> UserAchievement:
    user_achievement = achievement_crud.get_user_achievement_by_id(db, user_achievement_id)
    if not user_achievement or user_achievement.user_id != user_id:
        raise ValueError("User achievement not found or not owned by user")

    if user_achievement.is_reward_received:
        raise ValueError("Reward already received for this achievement")

    return achievement_crud.update_user_achievement_reward_status(db, user_achievement, True)


def get_all_and_user_achievements(db: Session, user_id: int) -> dict[str, list]:
    all_achievements = achievement_crud.get_all_achievements(db)
    user_achievements = achievement_crud.list_user_achievements(db, user_id)
    return {
        "all_achievements": all_achievements,
        "user_achievements": user_achievements,
    }
