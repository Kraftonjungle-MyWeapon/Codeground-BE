from sqlalchemy.orm import Session
from src.app.domain.problem.crud.problem_crud import get_random_problem

TIER_PRIORITY = ["bronze", "silver", "gold", "platinum", "diamond", "challenger"]


def get_higher_tier(tier1: str, tier2: str):
    return max([tier1, tier2], key=lambda t: TIER_PRIORITY.index(t))


def select_problem_for_tiers(db: Session, tier1: str, tier2: str):
    selected_tier = get_higher_tier(tier1, tier2)
    return get_random_problem(db, selected_tier)
