from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.orm import Session
from src.app.core.database import get_db
from src.app.domain.report.service import report_service as service
from src.app.core.security import get_current_user
from src.app.models.models import User
from src.app.domain.match.crud import match_crud

router = APIRouter()


@router.post("/", status_code=201)
async def create_report(
    game_id: int = Form(...), # game_id는 match_id로 사용
    reason: str = Form(...),
    description: str = Form(...),
    video: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # match_id를 사용하여 reported_user_id를 찾습니다.
    reported_user_id = match_crud.get_match_opponent_id(db, game_id, current_user.user_id)

    if reported_user_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reported user not found in this match.")

    await service.save_report(db, game_id, reason, description, video, reported_user_id, current_user.user_id)
    return {"message": "Report received"}
