from sqlalchemy.orm import Session
from sqlalchemy import func
from src.app.models.models import User, CheatReport, Problem, MatchLog, UserMmr
from src.app.models.models import Achievement, Match, AchievementPrerequisite # Added Match, AchievementPrerequisite
from src.app.domain.admin.schemas.admin_schemas import AchievementCreate, AchievementUpdate, AdminProblemUpdate # Added AdminProblemUpdate
from src.app.utils.s3_utils import issue_problem_urls, upload_bytes # Added S3 utilities
from typing import Optional, List, Dict # Added for type hints
from src.app.config.config import settings, BASE_DIR # Added settings, BASE_DIR
from pathlib import Path # Added Path


ROOT_DIR = Path(__file__).resolve().parents[5]
DATA_DIR = ROOT_DIR / "data"


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


# 7. 문제 삭제 (기존 함수는 사용하지 않음)
# def delete_problem(db: Session, problem_id: int):
#     problem = db.query(Problem).filter(Problem.problem_id == problem_id).first()
#     if problem:
#         db.delete(problem)
#         db.commit()
#         return True
#     return False

# New functions for problem management

async def get_problem_detail(db: Session, problem_id: int):
    problem = db.query(Problem).filter(Problem.problem_id == problem_id).first()
    if problem:
        s3_urls = await issue_problem_urls(problem)
        return problem, s3_urls
    return None, None

async def update_problem_and_s3_content(
    db: Session,
    problem_id: int,
    problem_update: AdminProblemUpdate,
    problem_body_content: Optional[str] = None,
    image_contents: Optional[Dict[str, bytes]] = None, # image_key: bytes
):
    db_problem = db.query(Problem).filter(Problem.problem_id == problem_id).first()
    if not db_problem:
        return None

    # Update DB fields
    update_data = problem_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None: # Only update if value is not None
            setattr(db_problem, key, value)

    # Update S3/Local content and update body_key/image_keys in DB
    if problem_body_content is not None:
        # Determine the key based on environment (S3 or local static)
        from src.app.config.config import settings
        from pathlib import Path # Ensure Path is imported

        if settings.ENV == "local":
            # For local, save to data directory and update body_key to logical path
            logical_body_key = f"problems/{problem_id}.json"
            local_body_path = DATA_DIR / logical_body_key
            local_body_path.parent.mkdir(parents=True, exist_ok=True)
            with open(local_body_path, "w", encoding="utf-8") as f:
                f.write(problem_body_content)
            db_problem.body_key = logical_body_key
        else:
            # For server, upload to S3 and update body_key to S3 key
            s3_body_key = f"problems/{problem_id}.json"
            upload_bytes(problem_body_content.encode('utf-8'), s3_body_key, bucket=settings.PROBLEM_BUCKET)
            db_problem.body_key = s3_body_key

    if image_contents:
        from src.app.config.config import settings
        from pathlib import Path # Ensure Path is imported

        new_image_keys = []
        for original_image_key, content_bytes in image_contents.items():
            if settings.ENV == "local":
                # For local, save to data directory and update image_key to logical path
                logical_image_key = f"problems/{problem_id}/images/{Path(original_image_key).name}"
                local_image_path = DATA_DIR / logical_image_key
                local_image_path.parent.mkdir(parents=True, exist_ok=True)
                with open(local_image_path, "wb") as fp:
                    fp.write(content_bytes)
                new_image_keys.append(logical_image_key)
            else:
                # For server, upload to S3 and update image_key to S3 key
                s3_image_key = f"problems/{problem_id}/images/{Path(original_image_key).name}"
                upload_bytes(content_bytes, s3_image_key, bucket=settings.PROBLEM_BUCKET)
                new_image_keys.append(s3_image_key)
        db_problem.image_keys = new_image_keys # Update the list of image keys in DB

    db.commit()
    db.refresh(db_problem)
    return db_problem

def delete_problem_and_related_matches(db: Session, problem_id: int):
    problem = db.query(Problem).filter(Problem.problem_id == problem_id).first()
    if not problem:
        return False

    # Update related MatchLog entries
    db.query(MatchLog).filter(MatchLog.problem_id == problem_id).update(
        {"problem_id": None}, synchronize_session=False # This will fail if problem_id is not nullable
    )
    # Update related Match entries
    db.query(Match).filter(Match.problem_id == problem_id).update(
        {"problem_id": None}, synchronize_session=False # This will fail if problem_id is not nullable
    )

    db.delete(problem)
    db.commit()
    return True


# 8. 티어별 유저 수(분포) 집계
def get_tier_distribution(db: Session):
    # 티어는 UserMmr.rating, 혹은 User 테이블에 별도 컬럼이 있으면 그걸 사용
    # 예시: 티어 산정 기준을 함수로 따로 만들 수도 있음
    tier_counts = db.query(UserMmr.rating, func.count(UserMmr.user_id)).group_by(UserMmr.rating).all()
    # 실제 서비스에서는 rating 구간별("bronze" 등)로 매핑하는 로직이 필요함
    return tier_counts


# 9. 특정 유저의 매칭/게임 히스토리 조회
def get_user_match_history(db: Session, user_id: int):
    return db.query(MatchLog).filter(MatchLog.user_id == user_id).all()


# 10. 전체 매칭 이력/검색 (필요시 페이징/필터 확장)
def get_all_match_logs(db: Session):
    return db.query(MatchLog).all()


# 11. [중요] 자동 영구 정지: 승인된 신고가 3초과일 때 is_banned 처리
# 11. 자동 영구 정지: 승인된 신고가 3초과일 때 is_banned 처리
def auto_ban_user_if_needed(db: Session, user_id: int, threshold: int = 3):
    count = (
        db.query(CheatReport).filter(CheatReport.reported_user_id == user_id, CheatReport.is_confirmed is True).count()
    )
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


def create_achievement(db: Session, achievement: AchievementCreate) -> Achievement:
    db_achievement = Achievement(**achievement.dict())
    db.add(db_achievement)
    db.commit()
    db.refresh(db_achievement)
    return db_achievement


def get_achievement(db: Session, achievement_id: int) -> Achievement | None:
    return db.query(Achievement).filter(Achievement.achievement_id == achievement_id).first()


def get_achievements(db: Session, skip: int = 0, limit: int = 100) -> list[Achievement]:
    return db.query(Achievement).offset(skip).limit(limit).all()


def update_achievement(db: Session, achievement_id: int, achievement: AchievementUpdate) -> Achievement | None:
    db_achievement = get_achievement(db, achievement_id)
    if db_achievement:
        for key, value in achievement.dict(exclude_unset=True).items():
            if key == "prerequisite_achievement_ids":
                # 기존 선행 업적 관계 삭제
                db.query(AchievementPrerequisite).filter(AchievementPrerequisite.achievement_id == achievement_id).delete()
                if value:
                    # 새로운 선행 업적 관계 추가
                    for prereq_id in value:
                        db_prereq = AchievementPrerequisite(
                            achievement_id=achievement_id,
                            prerequisite_achievement_id=prereq_id,
                        )
                        db.add(db_prereq)
            else:
                setattr(db_achievement, key, value)
        db.commit()
        db.refresh(db_achievement)
    return db_achievement


def delete_achievement(db: Session, achievement_id: int) -> Achievement | None:
    db_achievement = get_achievement(db, achievement_id)
    if db_achievement:
        db.delete(db_achievement)
        db.commit()
    return db_achievement
