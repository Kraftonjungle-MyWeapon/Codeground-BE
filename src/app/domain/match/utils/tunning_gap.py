from datetime import datetime
from src.app.domain.match.utils.mmr_measure import RD_MAX
from src.app.domain.match.schemas.match_schemas import MatchingUserInfo

# 튜닝 파라미터
G_MIN = 50  # 최소 허용치
K_RD = 50  # RD 가중치
K_TIME = 100  # 대기시간 가중치
T_MAX = 30.0  # 30초 경과 → time_term=1
# G_MIN + K_RD + K_TIME = 최대 격차
# G_MIN + K_RD = 뉴비가 매칭될 수 있는 격차에 해당


def personal_gap(user: MatchingUserInfo, *, now: datetime) -> float:
    rd_term = user.rd / RD_MAX
    waited = (now - user.joined_at).total_seconds()
    time_term = min(waited / T_MAX, 1.0)
    return G_MIN + K_RD * rd_term + K_TIME * time_term
