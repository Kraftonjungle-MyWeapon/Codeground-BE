from sqlalchemy.orm import Session
from sqlalchemy import func
from src.app.models.models import User, CheatReport, Problem, MatchLog, Match, Ranking, UserMmr

# 1. 유저 전체 목록 조회 (검색)
# nice to have -> 필터링 기능
def get_all_users(db: Session):
    return db.query(User).all()

# 2. 특정 유저 제재(영구 정지 처리)
def ban_user(db: Session, user_id: int):
    user = db.query(User).filter(User.user_id == user_id).first()
    if user and not user.is_banned:
        user.is_banned = True  # [수정] role이 아닌 is_banned로 관리
        db.commit()
        db.refresh(user)
    return user

# 2-1. 정지 해제 + 신고 카운트 초기화
def unban_user(db: Session, user_id: int):
    user = db.query(User).filter(User.user_id == user_id).first()
    if user and user.is_banned:
        user.is_banned = False
        db.commit()
        db.refresh(user)
        # 신고 무효화 (is_approved=True였던 걸 모두 False로 바꿈)
        db.query(CheatReport).filter(
            CheatReport.reported_user_id == user_id,
            CheatReport.is_approved == True
        ).update({"is_approved": False})
        db.commit()
    return user


# 3. 신고 리스트 조회
def get_all_reports(db: Session):
    return db.query(CheatReport).all()


# 4. 신고 승인/기각 처리
def update_report_status(db: Session, report_id: int, new_status: str):
    report = db.query(CheatReport).filter(CheatReport.report_id == report_id).first()
    if report:
        report.status = new_status  # 예: 'APPROVED' 또는 'REJECTED'
        db.commit()
        db.refresh(report)
    return report


# 5. 문제 리스트 조회
def get_all_problems(db: Session):
    return db.query(Problem).all()


# 6. 문제 승인/비승인 처리
def update_problem_approval(db: Session, problem_id: int, is_approved: bool):
    problem = db.query(Problem).filter(Problem.problem_id == problem_id).first()
    if problem:
        problem.is_approved = is_approved
        db.commit()
        db.refresh(problem)
    return problem


# 7. 문제 삭제
def delete_problem(db: Session, problem_id: int):
    problem = db.query(Problem).filter(Problem.problem_id == problem_id).first()
    if problem:
        db.delete(problem)
        db.commit()
        return True
    return False


# 8. 티어별 유저 수(분포) 집계
def get_tier_distribution(db: Session):
    # 티어는 UserMmr.rating, 혹은 User 테이블에 별도 컬럼이 있으면 그걸 사용
    # 예시: 티어 산정 기준을 함수로 따로 만들 수도 있음
    tier_counts = (
        db.query(UserMmr.rating, func.count(UserMmr.user_id))
        .group_by(UserMmr.rating)
        .all()
    )
    # 실제 서비스에서는 rating 구간별("bronze" 등)로 매핑하는 로직이 필요함
    return tier_counts


# 9. 특정 유저의 매칭/게임 히스토리 조회
def get_user_match_history(db: Session, user_id: int):
    return db.query(MatchLog).filter(MatchLog.user_id == user_id).all()


# 10. 전체 매칭 이력/검색 (필요시 페이징/필터 확장)
def get_all_match_logs(db: Session):
    return db.query(MatchLog).all()

# 11. 자동 영구 정지: 승인된 신고가 3초과일 때 is_banned 처리
def auto_ban_user_if_needed(db: Session, user_id: int, threshold: int = 3):
    count = db.query(CheatReport).filter(
        CheatReport.reported_user_id == user_id,
        CheatReport.is_confirmed == True
    ).count()
    user = db.query(User).filter(User.user_id == user_id).first()
    if user and count > threshold and not user.is_banned:
        user.is_banned = True
        db.commit()
        db.refresh(user)
        return True
    return False

# 12. 전체 유저 + 각 유저별 신고당한 횟수(report_count) 조회
def get_all_users_with_report_count(db: Session):
    from sqlalchemy.sql import func

    subq = (
        db.query(
            CheatReport.reported_user_id.label("user_id"),
            func.count(CheatReport.report_id).label("report_count")
        )
        .group_by(CheatReport.reported_user_id)
        .subquery()
    )

    result = (
        db.query(
            User,
            func.coalesce(subq.c.report_count, 0).label("report_count")
        )
        .outerjoin(subq, User.user_id == subq.c.user_id)
        .all()
    )
    return result