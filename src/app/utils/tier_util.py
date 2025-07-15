from src.app.domain.ranking.crud.ranking_crud import get_all_users_mmr
from sqlalchemy.orm import Session


def mmr_to_tier(mmr: int) -> str:
    if mmr < 500:
        return "bronze"
    elif 500 <= mmr < 1000:
        return "silver"
    elif 1000 <= mmr < 1500:
        return "gold"
    elif 1500 <= mmr < 2000:
        return "platinum"
    elif 2000 <= mmr < 2500:
        return "diamond"
    else:
        return "challenger"


def tier_to_mmr(tier: str) -> int:
    if tier == "bronze":
        return 0
    elif tier == "silver":
        return 500
    elif tier == "gold":
        return 1000
    elif tier == "platinum":
        return 1500
    elif tier == "diamond":
        return 2000
    else:
        return 2500


# 향후 매치 알고리즘 분리 시, 함께 이사갈 친구
tiers_cnt = {"bronze": 0, "silver": 0, "gold": 0, "platinum": 0, "diamond": 0, "challenger": 0}

tiers = ["bronze", "silver", "gold", "platinum", "diamond", "challenger"]


async def refresh_tier_cnt(db: Session) -> None:
    mmr_list = await get_all_users_mmr(db)

    for (mmr,) in mmr_list:
        tiers_cnt[mmr_to_tier(int(mmr))] += 1

    return
