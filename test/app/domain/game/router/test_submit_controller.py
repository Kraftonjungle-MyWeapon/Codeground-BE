from unittest.mock import patch
from fastapi.testclient import TestClient
from src.app.main import app

client = TestClient(app)


@patch("src.app.domain.game.service.game_service.stream_evaluate_code")
def test_submit_stream(mock_stream):
    async def gen():
        yield '{"type": "progress"}'
        yield '{"type": "final"}'

    mock_stream.return_value = gen()
    data = {"language": "python", "code": "print('hi')", "problem_id": "prob-001"}
    with client.stream("POST", "/api/v1/game/submit", json=data) as response:
        body = list(response.iter_lines())

    assert response.status_code == 200
    assert 'data: {"type": "progress"}' == body[0]
    assert 'data: {"type": "final"}' == body[2]
    mock_stream.assert_called_once_with("python", "print('hi')", "prob-001")


@patch("src.app.domain.game.service.game_service.stream_evaluate_code_public")
def test_submit_public_stream(mock_stream):
    async def gen():
        yield '{"type": "progress"}'
        yield '{"type": "final"}'

    mock_stream.return_value = gen()
    data = {"language": "python", "code": "print('hi')", "problem_id": "prob-001"}
    with client.stream("POST", "/api/v1/game/submit_public", json=data) as response:
        body = list(response.iter_lines())

    assert response.status_code == 200
    assert 'data: {"type": "progress"}' == body[0]
    assert 'data: {"type": "final"}' == body[2]
    mock_stream.assert_called_once_with("python", "print('hi')", "prob-001")