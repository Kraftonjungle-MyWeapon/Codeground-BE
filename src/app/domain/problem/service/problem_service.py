from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import UploadFile
from sqlalchemy.orm import Session

from src.app.config.config import settings
from src.app.models.models import Problem, ProblemDifficultyByTiers
from src.app.utils.s3_utils import upload_bytes
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
    env = (getattr(settings, "ENV", None) or getattr(settings, "ENVIRONMENT", None) or "local").lower()
    problem_uuid = str(uuid.uuid4())
    image_keys: List[str] = []

    if env == "local":
        body_path = DATA_DIR / f"{problem_uuid}.json"
        with open(body_path, "w", encoding="utf-8") as f:
            json.dump(problem_data.model_dump(), f, ensure_ascii=False)
        body_key = str(body_path)

        if images:
            for img in images:
                file_bytes = await img.read()
                img_path = DATA_DIR / f"{problem_uuid}_{img.filename}"
                with open(img_path, "wb") as fp:
                    fp.write(file_bytes)
                image_keys.append(str(img_path))
    else:
        body_key = f"problems/{problem_uuid}.json"
        json_bytes = json.dumps(problem_data.model_dump(), ensure_ascii=False).encode("utf-8")
        upload_bytes(json_bytes, body_key, bucket=settings.PROBLEM_BUCKET)

        if images:
            for idx, img in enumerate(images):
                file_bytes = await img.read()
                key = f"problems/{problem_uuid}/images/{idx}_{img.filename}"
                upload_bytes(file_bytes, key, bucket=settings.PROBLEM_BUCKET)
                image_keys.append(key)

    new_problem = Problem(
        title=problem_data.title,
        category=problem_data.category,
        difficulty=ProblemDifficultyByTiers(problem_data.difficulty.lower()),
        body_key=body_key,
        image_keys=image_keys,
        language=problem_data.languages,
        problem_prefix=None,
        testcase_prefix=None,
    )

    return problem_crud.create_problem(db, new_problem)
