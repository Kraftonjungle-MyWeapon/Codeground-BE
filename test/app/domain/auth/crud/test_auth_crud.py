import pytest
from unittest.mock import MagicMock
from src.app.domain.auth.crud import auth_crud
from src.app.models.models import User
from src.app.domain.auth.schemas import auth_schemas


@pytest.mark.asyncio
async def test_get_user_by_email():
    # given
    mock_db = MagicMock()
    test_email = "test@test.com"
    expected_user = User(email=test_email, username="testuser")
    mock_db.query.return_value.filter.return_value.first.return_value = expected_user

    # when
    user = await auth_crud.get_user_by_email(mock_db, test_email)

    # then
    assert user == expected_user
    mock_db.query.assert_called_once_with(User)
    mock_db.query.return_value.filter.assert_called_once()


@pytest.mark.asyncio
async def test_get_by_email_existing():
    # given
    mock_db = MagicMock()
    test_email = "test@test.com"
    mock_db.query.return_value.filter.return_value.first.return_value = User(email=test_email)

    # when
    result = await auth_crud.get_by_email(mock_db, test_email)

    # then
    assert result is True


@pytest.mark.asyncio
async def test_get_by_email_not_existing():
    # given
    mock_db = MagicMock()
    test_email = "test@test.com"
    mock_db.query.return_value.filter.return_value.first.return_value = None

    # when
    result = await auth_crud.get_by_email(mock_db, test_email)

    # then
    assert result is False


@pytest.mark.asyncio
async def test_join_user():
    # given
    mock_db = MagicMock()
    sign_up_request = auth_schemas.UserSignupRequest(
        username="testuser", email="test@test.com", nickname="testnick", password="password"
    )

    # when
    new_user = await auth_crud.join_user(mock_db, sign_up_request)

    # then
    assert new_user.username == sign_up_request.username
    assert new_user.email == sign_up_request.email
    assert new_user.nickname == sign_up_request.nickname
    assert new_user.password == sign_up_request.password
    assert mock_db.add.call_count == 2
    mock_db.add.assert_any_call(new_user)
