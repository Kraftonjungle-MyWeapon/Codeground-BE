from typing import List, Optional
from pydantic import BaseModel


# 랭킹 한 줄 정보 (닉네임, 점수, 순위, 순위 변동)
class RankingEntry(BaseModel):
    user_id: int
    nickname: str
    profile_img_url: Optional[str] = None
    mmr: int
    rank: int
    rank_diff: Optional[int] = 0


# 랭킹 리스트 응답
class RankingListResponse(BaseModel):
    language: str
    rankings: List[RankingEntry]


# 갱신 완료 후 업데이트 수량/로그 수량
class RankingRefreshResponse(BaseModel):
    updated: int  # 갱신된 랭킹 개수
    logs: int  # 기록된 변동 로그 개수


# 메시지 + 갱신 결과 담기 용도
class MessageResponse(BaseModel):
    message: str
    details: Optional[RankingRefreshResponse] = None
