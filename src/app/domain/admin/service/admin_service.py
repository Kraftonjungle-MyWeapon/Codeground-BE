from sqlalchemy.orm import Session
from src.app.domain.admin.crud import admin_crud
from src.app.models.models import CheatReport

# 1. 유저 영구정지
def ban_user_service(db: Session, user_id: int):
    user = admin_crud.ban_user(db, user_id)
    return user

# 2. 유저 정지 해제
def unban_user_service(db: Session, user_id: int):
    user = admin_crud.unban_user(db, user_id)
    return user

# 3. 신고 목록 조회
def get_all_reports_service(db: Session):
    return admin_crud.get_all_reports(db)

# 4. 신고 승인(승인+자동 밴까지)
def confirm_report_service(db: Session, report_id: int):
    report = db.query(CheatReport).filter(CheatReport.report_id == report_id).first()
    if not report:
        return None
    if report.is_confirmed:
        return "already_confirmed"
    report.is_confirmed = True
    db.commit()
    db.refresh(report)
    # 자동 밴
    admin_crud.auto_ban_user_if_needed(db, report.reported_user_id)
    return report

# 5. 문제 리스트 조회
def get_all_problems_service(db: Session):
    return admin_crud.get_all_problems(db)

# 6. 문제 승인/비승인 처리
def approve_problem_service(db: Session, problem_id: int, is_approved: bool):
    return admin_crud.update_problem_approval(db, problem_id, is_approved)

# 7. 티어 분포 집계
def get_tier_distribution_service(db: Session):
    return admin_crud.get_tier_distribution(db)
