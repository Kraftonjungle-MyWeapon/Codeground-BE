from fastapi import APIRouter, Depends, HTTPException, Request, File, UploadFile, Form
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
    nickname: str = Form(None),
    current_password: str = Form(None),
    new_password: str = Form(None),
    profile_image: UploadFile = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    logger.info(f"Updating user profile for user ID: {current_user.user_id}")
    profile_img_url_str = None
    if profile_image:
        from src.app.utils.image_utils import upload_profile_image
        profile_img_url_str = await upload_profile_image(profile_image)

    updated_user = await service.update_my_profile(
        db=db,
        user_id=current_user.user_id,
        nickname=nickname,
        current_password=current_password,
        new_password=new_password,
        profile_img_url=profile_img_url_str,
    )
    if not updated_user:
        logger.warning(f"Failed to update user profile for user ID: {current_user.user_id}")
        raise HTTPException(status_code=400, detail="Failed to update user info")
    logger.info(f"Successfully updated profile for user ID: {current_user.user_id}")

    user_mmr = await get_mmr_by_id(db, updated_user.user_id)
    mmr = user_mmr.rating if user_mmr and user_mmr.rating else 1000
    user_rank_info = await get_rank_by_id(db, updated_user.user_id)
    rank = user_rank_info.rank if user_rank_info else 0

    user_dict = {
        "user_id": updated_user.user_id,
        "email": updated_user.email,
        "nickname": updated_user.nickname,
        "username": updated_user.username,
        "use_lang": updated_user.use_lang,
        "profile_img_url": updated_user.profile_img_url,
        "user_mmr": int(mmr),
        "user_rank": int(rank),
    }


    return schemas.UserUpdateResponse(
        message="회원 정보가 성공적으로 수정되었습니다.",
        user=schemas.UserResponseDto(**user_dict),
    )


@router.delete("/me")
async def delete_my_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """회원 탈퇴 처리."""
    logger.info(f"Deleting account for user ID: {current_user.user_id}")
    success = await service.delete_my_account(db, current_user.user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "회원 탈퇴가 완료되었습니다."}
