from sqlalchemy.orm import Session
from sqlalchemy import func
from src.app.models.models import Problem, ProblemDifficultyByTiers

async def get_random_problem(db: Session, tier : str) -> type[Problem]:
    try:
        tier_enum = ProblemDifficultyByTiers(tier.lower())  # 문자열 → Enum
    except ValueError:
        raise ValueError(f"Invalid tier: {tier}")

    problem = db.query(Problem).filter(Problem.difficulty == tier_enum).order_by(func.random()).first()
    if problem is None:
        raise Exception("No problems exist")
    return problem
