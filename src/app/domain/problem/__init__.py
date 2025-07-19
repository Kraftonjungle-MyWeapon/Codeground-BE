from fastapi import APIRouter

from .router import problem_controller

router = APIRouter()
router.include_router(problem_controller.router, prefix="/problem", tags=["Problem"])
