from fastapi import HTTPException, status, UploadFile
from sqlalchemy.orm import Session
from src.app.domain.user.crud import user_crud as crud
from src.app.domain.user.schemas import user_schemas as schemas
from src.app.core.password import get_password_hash, verify_password as verify_pw
from src.app.utils.logging import logger
from src.app.utils.s3_utils import PROFILE_IMAGE_BUCKET, s3
from src.app.models.models import UserMmr
from src.app.domain.match.crud.match_crud import get_mmr_by_id
import uuid


async def get_user_data(db: Session, input_id: int) -> schemas.UserDto:
    logger.info(f"Attempting to retrieve user data for ID: {input_id}")
    user = crud.get_user_by_id(db, input_id=input_id)
    if not user:
        logger.warning(f"User with ID {input_id} not found.")
        raise HTTPException(status_code=404, detail="User not found")
    logger.info(f"Successfully retrieved user data for ID: {input_id}")
    return schemas.UserDto.model_validate(user)


async def update_my_profile(
    db: Session,
    user_id: int,
    nickname: str | None,
    current_password: str | None,
    new_password: str | None,
    use_lang: str | None,
    user_mmr: int | None,
    profile_image: UploadFile | None = None,
):
    logger.info(f"Attempting to update profile for user ID: {user_id}")
    user = crud.get_user_by_id(db, user_id)

    if not user:
        logger.warning(f"User with ID {user_id} not found for profile update.")
        raise HTTPException(status_code=404, detail="User not found")

    if new_password:
        if not current_password:
            logger.warning(f"Current password not provided for user {user_id} during password change.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="현재 비밀번호를 입력해야 합니다.",
            )
        if not await verify_pw(current_password, user.password):
            logger.warning(f"Incorrect current password for user {user_id} during password change.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="현재 비밀번호가 일치하지 않습니다.",
            )
        user.password = get_password_hash(new_password)
        logger.info(f"Password updated for user ID: {user_id}")

    if nickname is not None:
        if user.nickname != nickname:
            user.nickname = nickname
            logger.info(f"Nickname updated for user ID: {user_id}")
        else:
            logger.info(f"Nickname updated for user ID: {user_id}")

    if use_lang is not None:
        user.use_lang = use_lang
        logger.info(f"Use language updated for user ID: {user_id}")

    if user_mmr is not None:
        user_mmr_obj = await get_mmr_by_id(db, user_id)
        if user_mmr_obj:
            user_mmr_obj.rating = float(user_mmr)
            db.add(user_mmr_obj)
            db.commit()
            db.refresh(user_mmr_obj)
            logger.info(f"User MMR updated for user ID: {user_id} to {user_mmr_obj.rating}")
        else:
            # If UserMmr object does not exist, create a new one
            new_mmr_obj = UserMmr(user_id=user_id, rating=float(user_mmr))
            db.add(new_mmr_obj)
            db.commit()
            db.refresh(new_mmr_obj)
            logger.info(f"New User MMR created for user ID: {user_id} with rating {user_mmr}")

    if profile_image:
        contents = await profile_image.read()  # ✅ 한 번만 읽고
        unique_filename = f"{uuid.uuid4()}-{profile_image.filename}"
        s3_key = f"profile_images/{unique_filename}"
        try:
            s3.put_object(Bucket=PROFILE_IMAGE_BUCKET, Key=s3_key, Body=contents)  # ✅ 직접 업로드
            user.profile_img_url = s3_key
            logger.info(f"Profile image uploaded to {s3_key} for user ID: {user_id}")
        except Exception as e:
            logger.error(f"Failed to upload profile image for user {user_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to upload profile image")

    crud.update_user(db, user)
    logger.info(f"Profile update complete for user ID: {user_id}")
    return user


async def delete_my_account(db: Session, user_id: int) -> bool:
    """Delete the user account."""
    logger.info(f"Attempting to delete account for user ID: {user_id}")
    try:
        return crud.delete_user(db, user_id)
    except Exception as e:
        logger.error(f"Failed to delete user {user_id}: {e}")
        raise
