from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.app.core.database import get_db
from src.app.domain.ranking.service import ranking_service as service
from src.app.domain.ranking.schemas import ranking_schemas as schemas

router = APIRouter(prefix="/ranking", tags=["Ranking"])


@router.get("/", response_model=schemas.RankingListResponse)
async def get_ranking(
    language: str = "python3",
    db: Session = Depends(get_db),
):
    try:
        return await service.get_language_ranking(db, language)
    except Exception:
        return schemas.RankingListResponse(language=language, rankings=[])


# 모든 언어별 랭킹을 새로 계산해 업데이트하고, 변동 내역을 기록
@router.post("/refresh", summary="랭킹 갱신 (관리자용)")
async def refresh_ranking(db: Session = Depends(get_db)):

    try:
        result = await service.refresh_all_rankings(db)
        return {"message": "랭킹 갱신 완료", "details": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"랭킹 갱신 실패: {e}")
