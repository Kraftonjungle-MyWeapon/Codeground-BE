from fastapi import APIRouter
from .router import match_controller

router = APIRouter()
router.include_router(match_controller.router, prefix="/match", tags=["match"])
