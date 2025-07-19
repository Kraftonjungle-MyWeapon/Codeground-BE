from sqlalchemy.orm import Session
from src.app.models.models import CheatReport


def create_report(
    db: Session, game_id: int | None, reason: str, description: str, video_path: str, reported_user_id: int, reporter_user_id: int
) -> CheatReport:
    report = CheatReport(
        game_id=game_id,
        reason=reason,
        description=description,
        video_path=video_path,
        reported_user_id=reported_user_id,
        reporter_user_id=reporter_user_id,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def get_report_count_for_user(db: Session, user_id: int):
    return db.query(CheatReport).filter(CheatReport.reported_user_id == user_id).count()
