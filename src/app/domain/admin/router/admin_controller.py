from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import json
from pathlib import Path
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
    AdminProblemDetailOut,  # Added
    AdminProblemUpdate,  # Added
)
from src.app.domain.admin.service import admin_service
from src.app.utils.tier_util import mmr_to_tier
from src.app.domain.ranking.crud.ranking_crud import get_all_users_mmr
from src.app.domain.achievement.service import achievement_service
from src.app.models.models import AchievementTriggerType
from src.app.config.config import settings
from src.app.utils.s3_utils import issue_problem_urls  # Added
from datetime import datetime

ROOT_DIR = Path(__file__).resolve().parents[5]

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
    return [
        AdminProblemOut(
            problem_id=p.problem_id,
            title=p.title,
            difficulty=p.difficulty,
            is_approved=p.is_approved,
            created_at=p.created_at,
            author_id=p.author_id,
            category=p.category,
            language=p.language,
        )
        for p in problems
    ]


# (7) 특정 문제의 승인/비승인 상태를 처리하는 엔드포인트
@router.patch("/problems/{problem_id}/approve", response_model=AdminProblemApproveResult)
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


@router.get("/problems/{problem_id}", response_model=AdminProblemDetailOut)
async def get_problem_by_id(problem_id: int, db: Session = Depends(get_db)):
    if settings.ENV == "local":
        local_json_path = os.path.join(ROOT_DIR, "data", "35.json")
        if not os.path.exists(local_json_path):
            raise HTTPException(status_code=404, detail="Local problem data not found")
        with open(local_json_path, "r", encoding="utf-8") as f:
            local_data = json.load(f)
        base_static_url = "http://localhost:8000/static/problems/"
        problem_file_name = "35.json"

        static_image_urls = [
            f"{base_static_url}img_1752665674274_aws_leetcode_battle_anticheat_24-AWS_LeetCode_Battle.png",
            f"{base_static_url}img_1752665694489_1.png"
        ]

        return AdminProblemDetailOut(
            problem_id=problem_id,  # Use the requested problem_id
            title=local_data.get("title", "Local Problem"),
            difficulty=local_data.get("difficulty", "bronze"),
            is_approved=True,
            created_at=datetime.now(),
            author_id=1,  # Dummy author_id
            category=local_data.get("category", ["local"]),
            language=local_data.get("language", ["python3"]),
            problem_url=f"{base_static_url}{problem_file_name}", # Use static URL
            image_urls=static_image_urls, # Use static URLs for images
            problem_prefix=local_data.get("problem_prefix", ""),
            testcase_prefix=local_data.get("testcase_prefix", ""),
        )

    # Original logic for server environment
    problem, s3_urls = await admin_crud.get_problem_detail(db, problem_id)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    return AdminProblemDetailOut(
        problem_id=problem.problem_id,
        title=problem.title,
        difficulty=problem.difficulty,
        is_approved=problem.is_approved,
        created_at=problem.created_at,
        author_id=problem.author_id,
        category=problem.category,
        language=problem.language,
        problem_url=s3_urls["problem_url"],
        image_urls=s3_urls["image_urls"],
        problem_prefix=problem.problem_prefix,
        testcase_prefix=problem.testcase_prefix,
    )


@router.patch("/problems/{problem_id}", response_model=AdminProblemOut)
async def update_problem_by_id(
    problem_id: int,
    problem_update_json: str = Form(...), # Changed to receive as JSON string
    problem_body_file: Optional[UploadFile] = File(None),
    image_files: Optional[List[UploadFile]] = File(None),
    db: Session = Depends(get_db),
):
    problem_update = AdminProblemUpdate.model_validate_json(problem_update_json) # Manually parse JSON string
    problem_body_content = None
    problem_body_content = None
    if problem_body_file:
        problem_body_content = (await problem_body_file.read()).decode("utf-8")

    image_contents = {}
    if image_files:
        # Fetch existing problem to get image_keys
        existing_problem, _ = await admin_crud.get_problem_detail(db, problem_id)
        if not existing_problem:
            raise HTTPException(status_code=404, detail="Problem not found")

        for i, file in enumerate(image_files):
            if i < len(existing_problem.image_keys):
                image_contents[existing_problem.image_keys[i]] = await file.read()
            else:
                # Handle new images if needed, for now, we only update existing ones
                pass

    updated_problem = await admin_crud.update_problem_and_s3_content(
        db, problem_id, problem_update, problem_body_content, image_contents
    )
    if not updated_problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    return AdminProblemOut(
        problem_id=updated_problem.problem_id,
        title=updated_problem.title,
        difficulty=updated_problem.difficulty,
        is_approved=updated_problem.is_approved,
        created_at=updated_problem.created_at,
        author_id=updated_problem.author_id,
        category=updated_problem.category,
        language=updated_problem.language,
    )


@router.delete("/problems/{problem_id}", status_code=204)
def delete_problem_by_id(problem_id: int, db: Session = Depends(get_db)):
    success = admin_crud.delete_problem_and_related_matches(db, problem_id)
    if not success:
        raise HTTPException(status_code=404, detail="Problem not found")
    return {"message": "Problem deleted successfully"}


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
