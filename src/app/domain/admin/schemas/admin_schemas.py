from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# 1. 유저 관리용 응답 스키마
class AdminUserOut(BaseModel):
    user_id: int
    email: str
    nickname: str
    is_banned: bool
    report_count: int
    created_at: datetime

    class Config:
        orm_mode = True

# 2. 신고(Report) 응답 스키마
class AdminReportOut(BaseModel):
    report_id: int
    reported_user_id: int
    reason: str
    description: Optional[str]
    is_approved: Optional[bool]
    created_at: datetime

    class Config:
        orm_mode = True

# 3. 문제(Problem) 응답 스키마
class AdminProblemOut(BaseModel):
    problem_id: int
    title: str
    difficulty: Optional[str]
    is_approved: Optional[bool]
    created_at: datetime

    class Config:
        orm_mode = True

# 4. 티어(또는 MMR) 분포 스키마
class TierDistributionItem(BaseModel):
    rating: float
    user_count: int

    class Config:
        orm_mode = True

# 5. 영구정지/해제 결과 등 단일 결과 응답
class AdminUserBanResult(BaseModel):
    user_id: int
    is_banned: bool

# 6. 신고 승인 결과
class AdminReportConfirmResult(BaseModel):
    report_id: int

# 7. 문제 승인 결과
class AdminProblemApproveResult(BaseModel):
    problem_id: int
    is_approved: bool
