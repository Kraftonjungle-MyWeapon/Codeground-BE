import httpx
import websockets
import json
from fastapi import HTTPException
from src.app.config.config import settings
from sqlalchemy.orm import Session
from src.app.domain.game.router.game_controller import process_match_result
from src.app.domain.match.crud.match_crud import get_log_by_game_id
from src.app.domain.game.service import game_result_service
from src.app.utils.logging import logger


async def evaluate_code(language: str, code: str):
    logger.info(f"Evaluating code with language: {language}")
    payload = {
        "language": language,
        "code": code,
        "stdins": [],
        "timeLimit": 30000,
        "memoryLimit": 256,
        "token": None,
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(settings.ONLINE_JUDGE_HOST_ENDPOINT, json=payload)
            response.raise_for_status()
            results = response.json()
            logger.info(f"Code evaluation successful for language: {language}")
        except httpx.HTTPStatusError as e:
            logger.error(f"Judge request failed: {e.response.status_code} - {e.response.text}")
            raise HTTPException(status_code=e.response.status_code, detail="Judge request failed")
        except httpx.HTTPError as e:
            logger.error(f"Judge service unreachable: {e}")
            raise HTTPException(status_code=500, detail="Judge service unreachable")
    success = all(res.get("exitCode") == 0 for res in results)
    return {"result": "correct" if success else "wrong", "detail": results}


async def stream_evaluate_code(db: Session, user_id: int, match_id: int, language: str, code: str, problem_id: str):
    """Submit code to the judge service using /execute_v4 and stream results.

    This function returns an async generator yielding raw JSON messages received
    from the judge backend WebSocket. Each yielded value is a JSON formatted
    string representing either a progress or final message.
    """
    logger.info(f"Streaming code evaluation for user {user_id}, match {match_id}, problem {problem_id}")
    base_url = settings.ONLINE_JUDGE_HOST_ENDPOINT.rsplit("/", 1)[0]
    execute_url = f"{base_url}/execute_v4"
    payload = {
        "language": language,
        "code": code,
        "problemId": problem_id,
        "token": None,
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(execute_url, json=payload)
            response.raise_for_status()
            request_id = response.json().get("requestId")
            logger.info(f"Judge request successful for user {user_id}, match {match_id}. Request ID: {request_id}")
        except httpx.HTTPStatusError as e:
            logger.error(f"Judge request failed for user {user_id}, match {match_id}: {e.response.status_code} - {e.response.text}")
            raise HTTPException(status_code=e.response.status_code, detail="Judge request failed")
        except httpx.HTTPError as e:
            logger.error(f"Judge service unreachable for user {user_id}, match {match_id}: {e}")
            raise HTTPException(status_code=500, detail="Judge service unreachable")

    scheme, rest = execute_url.split("://", 1)
    ws_scheme = "wss" if scheme == "https" else "ws"
    ws_url = f"{ws_scheme}://{rest.split('/')[0]}/ws/progress/{request_id}"

    async with websockets.connect(ws_url) as websocket:  # type: ignore[attr-defined]
        async for message in websocket:
            yield message
            if '"type":"final"' in message or '"type": "final"' in message:
                # Parse the final message to extract the result
                final_message = json.loads(message)
                # Assuming 'result' is present in the final message from the judge service
                result = final_message.get("status")
                if result == "success":
                    log = await get_log_by_game_id(db, match_id, user_id)
                    opponent_id = log.opponent_id
                    await process_match_result(db, match_id, user_id, opponent_id, "finish")
                break

async def stream_evaluate_code_public(language: str, code: str, problem_id: str):
    """Submit code to the judge service using /execute_v4_public and stream results.

    This mirrors :func:`stream_evaluate_code` but only evaluates against public
    test cases. It yields raw JSON strings received from the judge backend
    websocket until a final message is sent.
    """
    logger.info(f"Streaming public code evaluation for problem {problem_id}")
    base_url = settings.ONLINE_JUDGE_HOST_ENDPOINT.rsplit("/", 1)[0]
    execute_url = f"{base_url}/execute_v4_public"
    payload = {
        "language": language,
        "code": code,
        "problemId": problem_id,
        "token": None,
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(execute_url, json=payload)
            response.raise_for_status()
            request_id = response.json().get("requestId")
            logger.info(f"Public judge request successful for problem {problem_id}. Request ID: {request_id}")
        except httpx.HTTPStatusError as e:
            logger.error(f"Public judge request failed for problem {problem_id}: {e.response.status_code} - {e.response.text}")
            raise HTTPException(status_code=e.response.status_code, detail="Judge request failed")
        except httpx.HTTPError as e:
            logger.error(f"Public judge service unreachable for problem {problem_id}: {e}")
            raise HTTPException(status_code=500, detail="Judge service unreachable")

    scheme, rest = execute_url.split("://", 1)
    ws_scheme = "wss" if scheme == "https" else "ws"
    ws_url = f"{ws_scheme}://{rest.split('/')[0]}/ws/progress/{request_id}"

    async with websockets.connect(ws_url) as websocket:  # type: ignore[attr-defined]
        async for message in websocket:
            yield message
            if '"type":"final"' in message or '"type": "final"' in message:
                break