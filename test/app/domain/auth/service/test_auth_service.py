import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from src.app.domain.auth.service import auth_service
from src.app.domain.auth.schemas import auth_schemas


@pytest.mark.asyncio
async def test_join_fail():
    # given
    mock_db = MagicMock()
    sign_up_request = auth_schemas.UserSignupRequest(
        username="testuser", email="test@test.com", nickname="testnick", password="password"
    )
    with (
        patch("src.app.domain.auth.crud.auth_crud.join_user", return_value=None) as mock_join_user,
        patch(
            "src.app.domain.auth.service.auth_service.get_password_hash", return_value="hashed_password"
        ) as mock_get_password_hash,
    ):
        # when / then
        with pytest.raises(HTTPException) as exc_info:
            await auth_service.join(mock_db, sign_up_request)
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Fail Sign Up User"
        mock_get_password_hash.assert_called_once_with("password")
        mock_join_user.assert_called_once()


@pytest.mark.asyncio
async def test_authenticate_user_not_found():
    # given
    mock_db = MagicMock()
    with patch("src.app.domain.auth.crud.auth_crud.get_user_by_email", return_value=None) as mock_get_user:
        # when / then
        with pytest.raises(HTTPException) as exc_info:
            await auth_service.authenticate_user(mock_db, "nonexistent@test.com", "password")
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid User Data"
        mock_get_user.assert_called_once_with(db=mock_db, email="nonexistent@test.com")


@pytest.mark.asyncio
async def test_authenticate_user_wrong_password():
    # given
    mock_db = MagicMock()
    user_in_db = MagicMock()
    user_in_db.email = "test@test.com"
    user_in_db.username = "testuser"
    user_in_db.nickname = "testnick"
    user_in_db.password = "hashed_password"  # This is the hashed password in the DB

    with (
        patch("src.app.domain.auth.crud.auth_crud.get_user_by_email", return_value=user_in_db) as mock_get_user,
        patch("src.app.domain.auth.service.auth_service.verify_password", return_value=False) as mock_verify_password,
    ):
        # when / then
        with pytest.raises(HTTPException) as exc_info:
            await auth_service.authenticate_user(mock_db, "test@test.com", "wrong_password")
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid Password"
        mock_get_user.assert_called_once_with(db=mock_db, email="test@test.com")
        mock_verify_password.assert_called_once_with("wrong_password", "hashed_password")
