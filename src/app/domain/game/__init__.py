from fastapi import APIRouter
from .router import game_controller, submit_controller

router = APIRouter()
router.include_router(game_controller.router, prefix="/game", tags=["game"])
router.include_router(submit_controller.router, prefix="/game", tags=["submit"])
