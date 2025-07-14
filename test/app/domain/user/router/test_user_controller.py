from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from src.app.main import app
from src.app.core.database import get_db
from src.app.core.security import get_current_user

app.dependency_overrides[get_db] = lambda: MagicMock()
app.dependency_overrides[get_current_user] = lambda: MagicMock(user_id=1)
client = TestClient(app)

@patch("src.app.domain.user.service.user_service.delete_my_account", return_value=True)
def test_delete_my_account_success(mock_delete):
    response = client.delete("/api/v1/user/me")
    assert response.status_code == 200
    assert response.json() == {"message": "회원 탈퇴가 완료되었습니다."}
    mock_delete.assert_called_once()
