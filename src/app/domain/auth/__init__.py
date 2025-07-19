from fastapi import APIRouter
from .router import auth_controller

router = APIRouter()
router.include_router(auth_controller.router, tags=["auth"])
