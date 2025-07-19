from typing import List

from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session

from src.app.core.database import get_db
from src.app.domain.problem.service import problem_service as service
from src.app.domain.problem.schemas import problem_schemas as schemas

router = APIRouter()


@router.post("/", status_code=201, response_model=schemas.ProblemCreateResponse)
async def create_problem(
    problem: str = Form(...),
    images: List[UploadFile] | None = File(None),
    db: Session = Depends(get_db),
):
    problem_data = schemas.ProblemCreateRequest.parse_raw(problem)
    new_problem = await service.save_problem(db, problem_data, images)
    return schemas.ProblemCreateResponse(problem_id=new_problem.problem_id)
