from fastapi import APIRouter
from .router import report_controller

router = APIRouter()
router.include_router(report_controller.router, prefix="/report", tags=["Report"])
