from datetime import datetime
from dataclasses import dataclass
from typing import Optional
from pydantic import BaseModel
from src.app.models.models import MatchResult, ProblemDifficultyByTiers


@dataclass
class MatchingUserInfo:
    id: int
    mmr: float
    rd: float
    joined_at: datetime


class MatchLogSchema(BaseModel):
    result: Optional[MatchResult]
    opponent_name: str
    mmr_earned: int
    opponent_tier: str
    game_difficulty: ProblemDifficultyByTiers
    game_time: datetime
    game_title: str

    class Config:
        from_attributes = True
