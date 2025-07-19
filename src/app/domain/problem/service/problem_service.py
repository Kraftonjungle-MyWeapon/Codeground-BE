from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from fastapi import UploadFile
from sqlalchemy.orm import Session

from src.app.config.config import settings
from src.app.models.models import Problem, ProblemDifficultyByTiers
from src.app.utils.s3_utils import upload_bytes, upload_image_to_s3_and_get_url
from src.app.domain.problem.crud import problem_crud

from ..schemas.problem_schemas import ProblemCreateRequest

ROOT_DIR = Path(__file__).resolve().parents[5]
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


async def save_problem(
    db: Session,
    problem_data: ProblemCreateRequest,
    images: Optional[List[UploadFile]] = None,
) -> Problem:
    # Create a new problem instance without the body_key first
    new_problem = Problem(
        title=problem_data.title,
        category=problem_data.category,
        difficulty=ProblemDifficultyByTiers(problem_data.difficulty.lower()),
        body_key="",  # Initially set to an empty string
        image_keys=[],  # Initially empty
        language=problem_data.languages,
        problem_prefix=None,
        testcase_prefix=None,
    )

    # Save the problem to the database to get an ID
    created_problem = problem_crud.create_problem(db, new_problem)
    problem_id = created_problem.problem_id

    env = (getattr(settings, "ENV", None) or getattr(settings, "ENVIRONMENT", None) or "local").lower()
    image_keys: List[str] = []

    if env == "local":
        # Save the problem data to a JSON file named with the problem ID
        body_path = DATA_DIR / f"{problem_id}.json"
        with open(body_path, "w", encoding="utf-8") as f:
            json.dump(problem_data.model_dump(), f, ensure_ascii=False)
        body_key = str(body_path)

        if images:
            problem_image_dir = DATA_DIR / str(problem_id) / "images"
            problem_image_dir.mkdir(parents=True, exist_ok=True)
            for img in images:
                file_bytes = await img.read()
                safe_filename = Path(img.filename).name
                img_path = problem_image_dir / safe_filename
                with open(img_path, "wb") as fp:
                    fp.write(file_bytes)
                image_keys.append(f"file://{img_path}")
    else:
        # Define the S3 key using the problem ID
        body_key = f"{problem_id}.json"
        json_bytes = json.dumps(problem_data.model_dump(), ensure_ascii=False).encode("utf-8")
        upload_bytes(json_bytes, body_key, bucket=settings.PROBLEM_BUCKET)

        if images:
            for img in images:
                file_bytes = await img.read()
                key = f"problems/images/{img.filename}"
                await upload_image_to_s3_and_get_url(file_bytes, key, settings.PROBLEM_BUCKET)
                image_keys.append(key)

    # Update the problem in the database with the S3 body_key and image_keys
    problem_crud.update_problem_keys(db, problem_id, body_key, image_keys)

    # Fetch the updated problem object to return
    updated_problem = db.query(Problem).filter(Problem.problem_id == problem_id).first()
    return updated_problem
