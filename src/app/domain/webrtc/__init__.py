from fastapi import APIRouter
from .router import webrtc_controller

router = APIRouter()
router.include_router(webrtc_controller.router, prefix="/ws", tags=["webrtc"])
