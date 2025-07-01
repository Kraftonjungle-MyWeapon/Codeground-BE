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
    password = Column(String(255), nullable=False)
    use_lang = Column(String(50), nullable=False, server_default="python3")  # 사용언어
    username = Column(String(255), nullable=False)
    nickname = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    role = Column(Enum(UserRole), nullable=False, server_default="USER")
    profile_img_url = Column(Text, nullable=True)  # 프로필 이미지 주소

    # 관계 설정
    match_logs = relationship("MatchLog", back_populates="user")
    mmr = relationship("UserMmr", uselist=False, back_populates="user")


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

    result = Column(Enum(MatchResult))
    mmr_earned = Column(Float, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
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
    problem_id = Column(Integer, ForeignKey("problem.problem_id"))

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
    title = Column(Text, nullable=False)
    category = Column(ARRAY(String), nullable=False)
    difficulty = Column(Enum(ProblemDifficultyByTiers), nullable=True)
    language = Column(ARRAY(String), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    problem_prefix = Column(Text, nullable=False)
    testcase_prefix = Column(Text, nullable=False)

    match = relationship("Match", back_populates="problem", uselist=False)
    match_logs = relationship("MatchLog", back_populates="problem")
