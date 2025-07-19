from sqlalchemy.orm import Session
from src.app.models.models import MatchLog


def get_match_logs_by_user_id(db: Session, user_id: int):
    return db.query(MatchLog).filter(MatchLog.user_id == user_id, MatchLog.result.isnot(None)).all()
