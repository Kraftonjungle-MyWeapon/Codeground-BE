from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from src.app.core.database import get_db
from src.app.domain.admin.crud import admin_crud
from src.app.domain.admin.schemas.admin_schemas import (
    AdminUserOut,
    AdminUserBanResult,
    AdminReportOut,
    AdminReportConfirmResult,
    AdminProblemOut,
    AdminProblemApproveResult,
    TierDistributionItem,
    AchievementCreate,
    AchievementUpdate,
    AchievementResponse,
)
from src.app.domain.admin.service import admin_service
from src.app.utils.tier_util import mmr_to_tier
from src.app.domain.ranking.crud.ranking_crud import get_all_users_mmr
from src.app.domain.achievement.service import achievement_service
from src.app.models.models import AchievementTriggerType

router = APIRouter(prefix="/admin", tags=["Admin"])


# (1) 전체 유저 목록을 조회하는 엔드포인트
@router.get("/users", response_model=List[AdminUserOut])
def get_all_users(db: Session = Depends(get_db)):
    users_with_reports = admin_crud.get_all_users_with_report_count(db)
    result = []
    for user, report_count in users_with_reports:
        result.append({
            "user_id": user.user_id,
            "email": user.email,
            "nickname": user.nickname,
            "is_banned": user.is_banned,
            "report_count": report_count,
            "created_at": user.created_at,
        })
    return result


# (2) 특정 유저를 영구정지 처리하는 엔드포인트
@router.post("/users/{user_id}/ban", response_model=AdminUserBanResult)
def ban_user(user_id: int, db: Session = Depends(get_db)):
    user = admin_crud.ban_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return AdminUserBanResult(user_id=user.user_id, is_banned=user.is_banned)


# (3) 특정 유저의 정지 상태를 해제하는 엔드포인트
@router.post("/users/{user_id}/unban", response_model=AdminUserBanResult)
def unban_user(user_id: int, db: Session = Depends(get_db)):
    user = admin_crud.unban_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return AdminUserBanResult(user_id=user.user_id, is_banned=user.is_banned)


# (4) 전체 신고 목록을 조회하는 엔드포인트
@router.get("/reports", response_model=List[AdminReportOut])
def get_all_reports(db: Session = Depends(get_db)):
    reports = admin_crud.get_all_reports(db)
    return reports


# (5) 특정 신고를 승인(확인) 처리하는 엔드포인트
@router.post("/reports/{report_id}/confirm", response_model=AdminReportConfirmResult)
def confirm_report(report_id: int, db: Session = Depends(get_db)):
    result = admin_service.confirm_report_service(db, report_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Report not found")
    if result == "already_confirmed":
        raise HTTPException(status_code=400, detail="Report already confirmed")
    return AdminReportConfirmResult(report_id=result.report_id, is_confirmed=result.is_confirmed)


# (6) 전체 문제 리스트를 조회하는 엔드포인트
@router.get("/problems", response_model=List[AdminProblemOut])
def get_all_problems(db: Session = Depends(get_db)):
    problems = admin_crud.get_all_problems(db)
    return problems


# (7) 특정 문제의 승인/비승인 상태를 처리하는 엔드포인트
@router.post("/problems/{problem_id}/approve", response_model=AdminProblemApproveResult)
async def approve_problem(problem_id: int, is_approved: bool, db: Session = Depends(get_db)):
    problem = admin_crud.update_problem_approval(db, problem_id, is_approved)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    # 문제가 승인되었고, 작성자가 있는 경우 업적 확인
    if is_approved and problem.author_id:
        await achievement_service.handle_achievement_event(
            db, problem.author_id, AchievementTriggerType.APPROVED_PROBLEM_COUNT
        )

    return AdminProblemApproveResult(problem_id=problem.problem_id, is_approved=problem.is_approved)


# (8) 전체 유저의 MMR과 티어 정보를 반환하는 엔드포인트 (분포 시각화용)
@router.get("/statistics/mmr-tier-list")
def get_mmr_tier_list(db: Session = Depends(get_db)):
    mmr_list = get_all_users_mmr(db)  # 동기 함수라 await 필요 없음
    return [{"mmr": int(mmr), "tier": mmr_to_tier(int(mmr))} for (mmr,) in mmr_list]


# (9) 티어별 유저 분포(집계) 통계를 반환하는 엔드포인트
@router.get("/statistics/tier-distribution", response_model=List[TierDistributionItem])
def get_tier_distribution(db: Session = Depends(get_db)):
    tier_data = admin_crud.get_tier_distribution(db)
    return [TierDistributionItem(rating=r, user_count=c) for r, c in tier_data]


# (10) 업적 관리 API
@router.post("/achievements", response_model=AchievementResponse)
def create_achievement(achievement: AchievementCreate, db: Session = Depends(get_db)):
    return admin_service.create_achievement(db=db, achievement=achievement)


@router.get("/achievements", response_model=List[AchievementResponse])
def get_achievements(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return admin_service.get_achievements(db=db, skip=skip, limit=limit)


@router.get("/achievements/{achievement_id}", response_model=AchievementResponse)
def get_achievement(achievement_id: int, db: Session = Depends(get_db)):
    db_achievement = admin_service.get_achievement(db, achievement_id=achievement_id)
    if db_achievement is None:
        raise HTTPException(status_code=404, detail="Achievement not found")
    return db_achievement


@router.put("/achievements/{achievement_id}", response_model=AchievementResponse)
def update_achievement(achievement_id: int, achievement: AchievementUpdate, db: Session = Depends(get_db)):
    return admin_service.update_achievement(db=db, achievement_id=achievement_id, achievement=achievement)


@router.delete("/achievements/{achievement_id}", response_model=AchievementResponse)
def delete_achievement(achievement_id: int, db: Session = Depends(get_db)):
    db_achievement = admin_service.delete_achievement(db, achievement_id=achievement_id)
    if db_achievement is None:
        raise HTTPException(status_code=404, detail="Achievement not found")
    return db_achievement
