from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from src.app.models.models import (
    MatchLog,
    MatchResult,
    Achievement,
    AchievementTriggerType,
    UserAchievement,
    Problem,
    Match,
)


def get_total_wins(db: Session, user_id: int) -> int:
    return (
        db.query(func.count())
        .select_from(MatchLog)
        .filter(
            MatchLog.user_id == user_id,
            MatchLog.result == MatchResult.WIN,
        )
        .scalar()
        or 0
    )


def get_total_losses(db: Session, user_id: int) -> int:
    return (
        db.query(func.count())
        .select_from(MatchLog)
        .filter(
            MatchLog.user_id == user_id,
            MatchLog.result == MatchResult.LOSS,
        )
        .scalar()
        or 0
    )


def get_total_draws(db: Session, user_id: int) -> int:
    return (
        db.query(func.count())
        .select_from(MatchLog)
        .filter(
            MatchLog.user_id == user_id,
            MatchLog.result == MatchResult.DRAW,
        )
        .scalar()
        or 0
    )


def get_total_problems_solved(db: Session, user_id: int) -> int:
    return (
        db.query(func.count(func.distinct(MatchLog.problem_id)))
        .filter(
            MatchLog.user_id == user_id,
            MatchLog.result == MatchResult.WIN,
        )
        .scalar()
        or 0
    )


def get_approved_problem_count(db: Session, user_id: int) -> int:
    return (
        db.query(func.count(Problem.problem_id))
        .filter(
            Problem.author_id == user_id,
            Problem.is_approved is True,
        )
        .scalar()
        or 0
    )


def get_match_duration_seconds(db: Session, match_id: int) -> int | None:
    match = db.query(Match).filter(Match.match_id == match_id).first()
    if match and match.finished_at and match.created_at:
        duration = match.finished_at - match.created_at
        return int(duration.total_seconds())
    return None


def get_consecutive_wins(db: Session, user_id: int) -> int:
    recent_matches = (
        db.query(MatchLog.result).filter(MatchLog.user_id == user_id).order_by(desc(MatchLog.created_at)).all()
    )
    count = 0
    for (result,) in recent_matches:
        if result == MatchResult.WIN:
            count += 1
        else:
            break
    return count


def get_consecutive_losses(db: Session, user_id: int) -> int:
    recent_matches = (
        db.query(MatchLog.result).filter(MatchLog.user_id == user_id).order_by(desc(MatchLog.created_at)).all()
    )
    count = 0
    for (result,) in recent_matches:
        if result == MatchResult.LOSS:
            count += 1
        else:
            break
    return count


def get_achievements_by_type(
    db: Session,
    trigger_type: AchievementTriggerType,
) -> list[Achievement]:
    return db.query(Achievement).filter(Achievement.trigger_type == trigger_type.value).order_by(Achievement.parameter).all()


def get_user_achievement(
    db: Session,
    user_id: int,
    achievement_id: int,
) -> UserAchievement | None:
    return (
        db.query(UserAchievement)
        .filter(
            UserAchievement.user_id == user_id,
            UserAchievement.achievement_id == achievement_id,
        )
        .first()
    )


def get_user_achievement_by_id(
    db: Session,
    user_achievement_id: int,
) -> UserAchievement | None:
    return db.query(UserAchievement).filter(UserAchievement.user_achievement_id == user_achievement_id).first()


def create_user_achievement(
    db: Session,
    user_id: int,
    achievement_id: int,
) -> UserAchievement:
    ua = UserAchievement(user_id=user_id, achievement_id=achievement_id)
    db.add(ua)
    return ua


def list_user_achievements(db: Session, user_id: int) -> list[UserAchievement]:
    return (
        db.query(UserAchievement)
        .filter(UserAchievement.user_id == user_id)
        .order_by(UserAchievement.achievement_id)
        .all()
    )


def update_user_achievement_reward_status(
    db: Session,
    user_achievement: UserAchievement,
    is_reward_received: bool,
) -> UserAchievement:
    user_achievement.is_reward_received = is_reward_received
    db.add(user_achievement)
    db.commit()
    db.refresh(user_achievement)
    return user_achievement


def get_all_achievements(db: Session) -> list[Achievement]:
    return db.query(Achievement).all()
