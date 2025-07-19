from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from src.app.core.database import get_db
from src.app.domain.analysis.service import analysis_service
from src.app.domain.analysis.schemas.analysis_schemas import WinRateResponse

router = APIRouter()


@router.get("/users/{user_id}/win-rate", response_model=WinRateResponse)
def get_user_win_rate(user_id: int, db: Session = Depends(get_db)):
    return analysis_service.get_user_win_rate(db, user_id)
