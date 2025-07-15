from sqlalchemy.orm import Session

from src.app.models.models import Problem


async def get_problem_by_id(db: Session, problem_id: int) -> type[Problem]:
    return db.query(Problem).filter(Problem.problem_id == problem_id).first()
