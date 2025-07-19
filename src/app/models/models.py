from src.app.core.database import Base
from sqlalchemy import Column, DateTime, Integer, String, func, Text, Float, ForeignKey, Enum, Boolean, text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import ARRAY
from enum import Enum as PyEnum


class UserRole(PyEnum):
    ADMIN = "ADMIN"
    USER = "USER"


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False)
    password = Column(String(255), nullable=True)
    github_id = Column(String(255), unique=True, nullable=True)
    use_lang = Column(String(50), nullable=False, server_default="python3")  # 사용언어
    username = Column(String(255), nullable=False)
    nickname = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    role = Column(Enum(UserRole), nullable=False, server_default="USER")
    is_banned = Column(
        Boolean, nullable=False, server_default=text("FALSE")
    )  # 영구 정지 여부 -> True면 해당 유저는 정지 상태
    profile_img_url = Column(Text, nullable=True)  # 프로필 이미지 주소
    last_login_at = Column(DateTime(timezone=True), nullable=True)  # 마지막 로그인 시각
    consecutive_login_days = Column(Integer, nullable=False, server_default="0")  # 연속 로그인 일수

    # 관계 설정
    match_logs = relationship("MatchLog", back_populates="user")
    mmr = relationship("UserMmr", uselist=False, back_populates="user")
    rankings = relationship("Ranking", back_populates="user")
    rank_change_logs = relationship("RankChangeLog", back_populates="user")
    user_achievements = relationship("UserAchievement", back_populates="user")  # 추가된 부분


class UserMmr(Base):
    __tablename__ = "user_mmr"
    mmr_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"))
    rating = Column(Float, nullable=False, server_default="1000")
    rating_devi = Column(Float, nullable=False, server_default="350")
    volatility = Column(Float, nullable=False, server_default="0.06")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 관계 설정
    user = relationship("User", back_populates="mmr")


class MatchResult(str, PyEnum):
    WIN = "win"
    DRAW = "draw"
    LOSS = "loss"


class MatchLog(Base):
    __tablename__ = "match_log"

    match_log_id = Column(Integer, primary_key=True, autoincrement=True)

    match_id = Column(Integer, ForeignKey("match.match_id"))
    match = relationship("Match", back_populates="logs")  # 관계 설정

    user_id = Column(Integer, ForeignKey("users.user_id"))
    user = relationship("User", back_populates="match_logs")  # 관계 설정

    problem_id = Column(Integer, ForeignKey("problem.problem_id"))
    problem = relationship("Problem", back_populates="match_logs")

    result = Column(Enum(MatchResult), nullable=True)
    submission_count = Column(Integer, default=0)  # 제출 횟수
    mmr_earned = Column(Float, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    opponent_id = Column(Integer, nullable=False)
    opponent_mmr = Column(Float, nullable=False)
    opponent_rd = Column(Float, nullable=False)
    is_consumed = Column(Boolean, server_default=text("FALSE"))


class MatchStatus(str, PyEnum):
    CREATED = "created"
    PENDING = "pending"
    RUNNING = "running"
    FINISH = "finish"


class MatchFinishStatus(str, PyEnum):
    ABNORMAL = "abnormal"
    NORMAL = "normal"
    ABSENT = "absent"
    DRAW = "draw"


class Match(Base):
    __tablename__ = "match"
    match_id = Column(Integer, primary_key=True, autoincrement=True)
    problem_id = Column(Integer, ForeignKey("problem.problem_id"), nullable=True)

    matching_status = Column(Enum(MatchStatus), server_default="CREATED")
    ending_status = Column(Enum(MatchFinishStatus))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 관계 설정
    logs = relationship("MatchLog", back_populates="match")
    problem = relationship("Problem", back_populates="match", uselist=False)


class ProblemDifficultyByTiers(str, PyEnum):
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"
    DIAMOND = "diamond"
    CHALLENGER = "challenger"


class Problem(Base):
    __tablename__ = "problem"
    problem_id = Column(Integer, primary_key=True, autoincrement=True)
    author_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)  # 문제 작성자
    title = Column(Text, nullable=False)
    category = Column(ARRAY(String), nullable=False)
    difficulty = Column(Enum(ProblemDifficultyByTiers), nullable=True)
    body_key = Column(Text, nullable=False)
    image_keys = Column(ARRAY(Text), nullable=True, default=list)
    language = Column(ARRAY(String), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    problem_prefix = Column(Text, nullable=True)
    testcase_prefix = Column(Text, nullable=True)
    is_approved = Column(Boolean, server_default=text("FALSE"))

    match = relationship("Match", back_populates="problem", uselist=False)
    match_logs = relationship("MatchLog", back_populates="problem")
    author = relationship("User")  # User와 관계 설정


class Ranking(Base):
    __tablename__ = "ranking"

    ranking_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    mmr = Column(Integer, nullable=False, index=True)
    language = Column(String, nullable=False, server_default="python3")
    rank = Column(Integer, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    rank_diff = Column(Integer, nullable=True, server_default="0")

    # 관계 설정
    user = relationship("User", back_populates="rankings")


class RankChangeLog(Base):
    __tablename__ = "rank_change_log"

    rank_change_log_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    old_rank = Column(Integer, nullable=True)
    new_rank = Column(Integer, nullable=True)
    change_value = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 관계 설정
    user = relationship("User", back_populates="rank_change_logs")


class CheatReport(Base):
    __tablename__ = "cheat_report"

    report_id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, nullable=True)
    reason = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    video_path = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    reported_user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)     # 신고 당한 사람 O, 신고를 한 사람 X
    reporter_user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)     # 신고를 한 사람 O
    is_approved = Column(Boolean, nullable=True)    # 관리자가 승인 O -> True, X -> False, 대기중 -> Null


# ———————————————— 사용자별 업적 진행 현황 ————————————————
class UserAchievement(Base):
    __tablename__ = "user_achievement"

    user_achievement_id = Column(Integer, primary_key=True, autoincrement=True)

    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    achievement_id = Column(Integer, ForeignKey("achievement.achievement_id"), nullable=False)

    # 누적형 업적의 진행 정도
    current_value = Column(Integer, nullable=False, server_default="0")

    # 보상 수령 여부
    is_reward_received = Column(Boolean, nullable=False, server_default=text("FALSE"))

    # 업적 달성 시각
    obtained_at = Column(DateTime(timezone=True), nullable=True)

    # 생성/수정 타임스탬프
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    modified_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 관계
    user = relationship("User", back_populates="user_achievements")
    achievement = relationship("Achievement", back_populates="user_achievements")


class RewardType(str, PyEnum):
    BADGE = "badge"
    POINT = "point"
    GIFT = "gift"
    # 필요시 더 추가 가능


class AchievementTriggerType(str, PyEnum):
    FIRST_WIN = "first_win"
    TOTAL_WIN = "total_win"
    CONSECUTIVE_WIN = "consecutive_win"
    TOTAL_LOSS = "total_loss"
    CONSECUTIVE_LOSS = "consecutive_loss"
    TOTAL_DRAW = "total_draw"
    PROBLEM_SOLVED = "problem_solved"
    WIN_WITHOUT_MISS = "win_without_miss"
    WIN_WITHIN_N_SUBMISSIONS = "win_within_n_submissions"
    FAST_WIN = "fast_win"
    APPROVED_PROBLEM_COUNT = "approved_problem_count"
    CONSECUTIVE_LOGIN = "consecutive_login"
    LOGIN_ON_DAY_OF_WEEK = "login_on_day_of_week"
    TOTAL_REPORTS_MADE = "total_reports_made"


# ———————————————— 업적 카테고리 ————————————————
class AchievementCategory(Base):
    __tablename__ = "achievement_category"

    achievement_category_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(String(255), nullable=True)
    image_url = Column(String(255), nullable=True)

    # 관계: 여러 업적이 하나의 카테고리에 속함
    achievements = relationship("Achievement", back_populates="category")


# ———————————————— 업적 정의 ————————————————
class Achievement(Base):
    __tablename__ = "achievement"

    achievement_id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)

    # — 카테고리 연결 —
    achievement_category_id = Column(Integer, ForeignKey("achievement_category.achievement_category_id"), nullable=True)
    category = relationship("AchievementCategory", back_populates="achievements")

    

    # — 보상 정보 —
    reward_type = Column(Enum(RewardType), nullable=False, server_default=RewardType.BADGE.value)
    reward_amount = Column(Integer, nullable=False, server_default="1")

    # — 기간 한정 업적 지원 —
    start_at = Column(DateTime(timezone=True), nullable=True)
    end_at = Column(DateTime(timezone=True), nullable=True)

    # — 통계용 필드 —
    unlocked_count = Column(Integer, nullable=False, server_default="0")

    # — 트리거 및 파라미터 —
    trigger_type = Column(Enum(AchievementTriggerType), nullable=False)
    parameter = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 관계: 사용자별 업적
    user_achievements = relationship("UserAchievement", back_populates="achievement")

    # 관계: 이 업적을 달성하기 위한 선행 업적들
    prerequisites = relationship(
        "AchievementPrerequisite",
        foreign_keys="[AchievementPrerequisite.achievement_id]",
        back_populates="achievement",
        cascade="all, delete-orphan"
    )
    # 관계: 이 업적이 선행 업적으로 사용되는 다른 업적들
    is_prerequisite_for = relationship(
        "AchievementPrerequisite",
        foreign_keys="[AchievementPrerequisite.prerequisite_achievement_id]",
        back_populates="prerequisite_achievement",
        cascade="all, delete-orphan"
    )


class AchievementPrerequisite(Base):
    __tablename__ = "achievement_prerequisite"

    achievement_id = Column(Integer, ForeignKey("achievement.achievement_id"), primary_key=True)
    prerequisite_achievement_id = Column(Integer, ForeignKey("achievement.achievement_id"), primary_key=True)

    # 관계
    achievement = relationship(
        "Achievement",
        foreign_keys=[achievement_id],
        back_populates="prerequisites"
    )
    prerequisite_achievement = relationship(
        "Achievement",
        foreign_keys=[prerequisite_achievement_id],
        back_populates="is_prerequisite_for"
    )
