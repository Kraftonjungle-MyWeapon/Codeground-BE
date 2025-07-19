import json
import os
from sqlalchemy.orm import Session
from src.app.models.models import Problem, ProblemDifficultyByTiers
from src.app.core.database import SessionLocal


def insert_problem_from_json(json_file_name):
    script_dir = os.path.dirname(__file__)
    project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
    json_path = os.path.join(project_root, json_file_name)
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    new_problems = Problem(
        title=data["title"],
        category=data["category"],  # ARRAY
        difficulty=ProblemDifficultyByTiers[data["difficulty"].upper()],  # Enum
        language=data["languages"],  # ARRAY
        problem_prefix=data.get("description", ""),  # 매핑: description → problem_prefix
        testcase_prefix=data.get("input_format", ""),  # 매핑: input_format → testcase_prefix
    )

    db: Session = SessionLocal()
    try:
        db.add(new_problems)
        db.commit()
    except Exception as e:
        db.rollback()
        print("문제 저장 중 오류:", e)
    finally:
        db.close()


json_files = [
    "data/prob-bronze.json",
    "data/prob-silver.json",
    "data/prob-gold.json",
    "data/prob-diamond.json",
    "data/prob-platinum.json",
    "data/prob-challenger.json",
]

for f in json_files:
    insert_problem_from_json(f)
