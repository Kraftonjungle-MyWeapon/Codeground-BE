from sqlalchemy.orm import Session
from src.app.domain.analysis.crud import analysis_crud
from src.app.domain.analysis.schemas.analysis_schemas import WinRateResponse
from src.app.models.models import MatchResult


def get_user_win_rate(db: Session, user_id: int) -> WinRateResponse:
    match_logs = analysis_crud.get_match_logs_by_user_id(db, user_id)

    win = 0
    loss = 0
    draw = 0

    for log in match_logs:
        if log.result == MatchResult.WIN:
            win += 1
        elif log.result == MatchResult.LOSS:
            loss += 1
        elif log.result == MatchResult.DRAW:
            draw += 1

    total_games = win + loss + draw
    win_rate = (win / total_games) * 100 if total_games > 0 else 0
    return WinRateResponse(win=win, loss=loss, draw=draw, win_rate=win_rate)
