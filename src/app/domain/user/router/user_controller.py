from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from src.app.core.database import get_db
from src.app.core.security import get_current_user
from src.app.domain.ranking.crud.ranking_crud import get_rank_by_id
from src.app.domain.user.schemas import user_schemas as schemas
from src.app.domain.user.service import user_service as service
from src.app.models.models import User
from src.app.domain.match.crud.match_crud import get_mmr_by_id
from src.app.utils.logging import logger

router = APIRouter()


@router.get("/me", response_model=schemas.UserResponseDto)
async def get_user_me(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    logger.info(f"Fetching user profile for user ID: {current_user.user_id}")
    try:
        user = await service.get_user_data(db, current_user.user_id)
        user_mmr = await get_mmr_by_id(db, user.user_id)
        mmr = user_mmr.rating if user_mmr.rating else 1000
        user_rank_info = await  get_rank_by_id(db, user.user_id)
        user_rank = user_rank_info.rank if user_rank_info else 00
        user_dict = user.model_dump()
        user_dict["user_mmr"] = int(mmr)
        user_dict["user_rank"] = int(user_rank)
        logger.info(f"Successfully fetched profile for user ID: {current_user.user_id}")
        return schemas.UserResponseDto(**user_dict)

    except Exception as e:
        logger.error(f"Error fetching user profile for user ID {current_user.user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/me", response_model=schemas.UserUpdateResponse)
async def update_my_profile_handler(
    update_data: schemas.UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    logger.info(f"Updating user profile for user ID: {current_user.user_id}")
    profile_img_url_str = str(update_data.profile_img_url) if update_data.profile_img_url else None

    updated_user = await service.update_my_profile(
        db,
        current_user.user_id,
        update_data.nickname,
        getattr(update_data, "current_password", None),
        update_data.new_password,
        profile_img_url_str,
    )
    if not updated_user:
        logger.warning(f"Failed to update user profile for user ID: {current_user.user_id}")
        raise HTTPException(status_code=400, detail="Failed to update user info")
    logger.info(f"Successfully updated profile for user ID: {current_user.user_id}")
    return schemas.UserUpdateResponse(
        message="회원 정보가 성공적으로 수정되었습니다.",
        user=schemas.UserResponseDto.model_validate(updated_user),
    )
