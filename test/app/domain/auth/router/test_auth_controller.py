from unittest.mock import patch
from fastapi.testclient import TestClient
from fastapi import HTTPException
from unittest.mock import MagicMock
from src.app.main import app
from src.app.core.database import get_db

app.dependency_overrides[get_db] = lambda: MagicMock()
client = TestClient(app)


@patch(
    "src.app.domain.auth.service.auth_service.check_duplicate_email",
    side_effect=HTTPException(status_code=400, detail="Email already registered"),
)
@patch("src.app.domain.auth.service.auth_service.join", return_value=True)
@patch("src.app.domain.auth.router.auth_controller.create_access_token", return_value="test_token")
@patch("src.app.domain.auth.service.auth_service.check_duplicate_nickname", return_value=False)
def test_sign_up_duplicate_email(mock_check_nick, mock_create_token, mock_join, mock_check_email):
    # given
    sign_up_data = {"email": "test@test.com", "username": "testuser", "password": "password", "nickname": "testnick"}

    # when
    response = client.post("/api/v1/auth/sign-up", json=sign_up_data)

    # then
    assert response.status_code == 400
    assert response.json() == {"detail": "Email already registered"}
    mock_check_email.assert_called_once()
    mock_join.assert_not_called()
    mock_create_token.assert_not_called()


@patch("src.app.domain.auth.service.auth_service.check_duplicate_email", return_value=False)
@patch(
    "src.app.domain.auth.service.auth_service.join",
    side_effect=HTTPException(status_code=400, detail="Fail Sign Up User"),
)
@patch("src.app.domain.auth.router.auth_controller.create_access_token", return_value="test_token")
@patch("src.app.domain.auth.service.auth_service.check_duplicate_nickname", return_value=False)
def test_sign_up_join_fail(mock_check_nick, mock_create_token, mock_join, mock_check_email):
    # given
    sign_up_data = {"email": "test@test.com", "username": "testuser", "password": "password", "nickname": "testnick"}

    # when
    response = client.post("/api/v1/auth/sign-up", json=sign_up_data)

    # then
    assert response.status_code == 400
    assert response.json() == {"detail": "Fail Sign Up User"}
    mock_check_email.assert_called_once()
    mock_join.assert_called_once()
    mock_create_token.assert_not_called()


@patch(
    "src.app.domain.auth.service.auth_service.authenticate_user",
    side_effect=HTTPException(status_code=401, detail="Invalid User Data"),
)
@patch("src.app.domain.auth.router.auth_controller.create_access_token", return_value="test_token")
def test_login_fail(mock_create_token, mock_authenticate_user):
    # given
    login_data = {"username": "test@test.com", "password": "password"}

    # when
    response = client.post("/api/v1/auth/login", data=login_data)

    # then
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid User Data"}
    mock_authenticate_user.assert_called_once()
    mock_create_token.assert_not_called()
