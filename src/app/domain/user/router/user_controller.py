from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.app.core.database import get_db
from src.app.core.security import get_current_user
from src.app.domain.user.schemas import user_schemas as schemas
from src.app.domain.user.service import user_service as service
from src.app.models.models import User

router = APIRouter()


@router.get("/me", response_model=schemas.UserResponseDto)
def get_user_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        user = service.get_user_data(db, current_user.user_id)
        return schemas.UserResponseDto.model_validate(user)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/me", response_model=schemas.UserUpdateResponse)
def update_my_profile_handler(
    update_data: schemas.UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    updated_user = service.update_my_profile(
        db,
        current_user.user_id,
        update_data.nickname,
        getattr(update_data, "current_password", None),
        update_data.new_password,
        update_data.profile_img_url,
    )
    if not updated_user:
        raise HTTPException(status_code=400, detail="Failed to update user info")
    return schemas.UserUpdateResponse(
        message="회원 정보가 성공적으로 수정되었습니다.",
        user=schemas.UserResponseDto.model_validate(updated_user),
    )
