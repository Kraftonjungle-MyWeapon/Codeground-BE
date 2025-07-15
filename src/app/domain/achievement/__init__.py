"""Achievement domain setup."""

from fastapi import APIRouter
from .router import achievement_controller

router = APIRouter()
router.include_router(achievement_controller.router, prefix="/achievements", tags=["achievement"])
