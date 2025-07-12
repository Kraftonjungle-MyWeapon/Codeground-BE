from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from src.app.core.database import get_db
from src.app.domain.admin.crud import admin_crud
from src.app.domain.admin.schemas.admin_schemas import (
    AdminUserOut, AdminUserBanResult,
    AdminReportOut, AdminReportConfirmResult,
    AdminProblemOut, AdminProblemApproveResult,
    TierDistributionItem,
)
from src.app.domain.admin.service import admin_service

router = APIRouter(
    prefix="/admin",
    tags=["Admin"]
)

# (1) 유저 전체 목록 조회
@router.get("/users", response_model=List[AdminUserOut])
def get_all_users(db: Session = Depends(get_db)):
    users = admin_crud.get_all_users(db)
    return users  # orm_mode=True이므로 객체 반환만으로 자동 직렬화

# (2) 특정 유저 영구정지 처리
@router.post("/users/{user_id}/ban", response_model=AdminUserBanResult)
def ban_user(user_id: int, db: Session = Depends(get_db)):
    user = admin_crud.ban_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return AdminUserBanResult(user_id=user.user_id, is_banned=user.is_banned)

# (3) 특정 유저 정지 해제
@router.post("/users/{user_id}/unban", response_model=AdminUserBanResult)
def unban_user(user_id: int, db: Session = Depends(get_db)):
    user = admin_crud.unban_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return AdminUserBanResult(user_id=user.user_id, is_banned=user.is_banned)

# (4) 신고 목록 조회
@router.get("/reports", response_model=List[AdminReportOut])
def get_all_reports(db: Session = Depends(get_db)):
    reports = admin_crud.get_all_reports(db)
    return reports

# (5) 신고 승인 처리(확인)
@router.post("/reports/{report_id}/confirm", response_model=AdminReportConfirmResult)
def confirm_report(report_id: int, db: Session = Depends(get_db)):
    result = admin_service.confirm_report_service(db, report_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Report not found")
    if result == "already_confirmed":
        raise HTTPException(status_code=400, detail="Report already confirmed")
    return AdminReportConfirmResult(report_id=result.report_id, is_confirmed=result.is_confirmed)

# (6) 문제 리스트 조회
@router.get("/problems", response_model=List[AdminProblemOut])
def get_all_problems(db: Session = Depends(get_db)):
    problems = admin_crud.get_all_problems(db)
    return problems

# (7) 문제 승인/비승인 처리
@router.post("/problems/{problem_id}/approve", response_model=AdminProblemApproveResult)
def approve_problem(problem_id: int, is_approved: bool, db: Session = Depends(get_db)):
    problem = admin_crud.update_problem_approval(db, problem_id, is_approved)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    return AdminProblemApproveResult(problem_id=problem.problem_id, is_approved=problem.is_approved)

# (8) 티어 분포 통계
@router.get("/statistics/tier-distribution", response_model=List[TierDistributionItem])
def get_tier_distribution(db: Session = Depends(get_db)):
    tier_data = admin_crud.get_tier_distribution(db)
    return [TierDistributionItem(rating=r, user_count=c) for r, c in tier_data]
