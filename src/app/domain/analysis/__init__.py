from fastapi import APIRouter
from .router import analysis_controller

router = APIRouter()
router.include_router(analysis_controller.router, prefix="/analysis", tags=["analysis"])
