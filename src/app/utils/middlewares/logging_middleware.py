import traceback
import json
from urllib.parse import parse_qs, urlencode
from fastapi import Request, HTTPException
from starlette.background import BackgroundTask
from starlette.responses import Response
from src.app.utils.logging import logger
from starlette.types import Message

SENSITIVE_KEYS = ["password", "access_token", "email", "username", "refresh_token"]


def partial_mask(value):
    if isinstance(value, str):
        length = len(value)
        return value[:2] + "*" * (length - 4) + value[-2:]
    return value


def sanitize_data(data, content_type):
    if isinstance(data, bytes):
        try:
            data = data.decode("utf-8")
        except UnicodeDecodeError:
            return "[binary data omitted]"

    if content_type == "application/json":
        try:
            data_json = json.loads(data)
            if isinstance(data_json, dict):
                return sanitize_dict(data_json)
            else:
                return data
        except (json.JSONDecodeError, TypeError):
            return data
    elif content_type == "application/x-www-form-urlencoded":
        data_dict = parse_qs(data)
        sanitized_dict = sanitize_dict({k: v[0] if isinstance(v, list) else v for k, v in data_dict.items()})
        return urlencode(sanitized_dict)
    else:
        return data


def sanitize_dict(data_dict):
    if not isinstance(data_dict, dict):
        return data_dict
    redacted_dict = {}
    for key, value in data_dict.items():
        if key.lower() in SENSITIVE_KEYS:
            redacted_dict[key] = partial_mask(value)
        elif isinstance(value, dict):
            redacted_dict[key] = sanitize_dict(value)
        else:
            redacted_dict[key] = value
    return redacted_dict


def log_info(level, url, req_body, content_type, status_code, res_body, res_content_type):
    if "multipart/form-data" in content_type:
        sanitized_req_body = "[multipart form-data omitted]"
    else:
        sanitized_req_body = sanitize_data(req_body, content_type)

    sanitized_res_body = sanitize_data(res_body, res_content_type)

    extra_info = {
        "request_url": str(url),
        "request_body": sanitized_req_body,
        "response_body": sanitized_res_body,
        "status_code": status_code,
    }

    if level == "info":
        logger.info("Request processed successfully", extra=extra_info)
    elif level == "warning":
        logger.warning("Request processed with warning", extra=extra_info)
    elif level == "error":
        logger.error("Request processed with error", extra=extra_info)


def log_error(url, req_body, content_type, error):
    if "multipart/form-data" in content_type:
        sanitized_req_body = "[multipart form-data omitted]"
    else:
        sanitized_req_body = sanitize_data(req_body, content_type)

    error_traceback = traceback.format_exc()
    extra_info = {
        "request_url": str(url),
        "request_body": sanitized_req_body,
        "error": str(error),
        "traceback": error_traceback,
    }
    logger.error("Error processing request", extra=extra_info)


async def set_body(request: Request, body: bytes):
    async def receive() -> Message:
        return {"type": "http.request", "body": body}

    request._receive = receive


async def log_requests(request: Request, call_next):
    # SSE 요청은 로깅하지 않음
    if request.headers.get("accept") == "text/event-stream":
        return await call_next(request)

    # docs 등은 제외
    if request.url.path.endswith("/") or request.url.path.endswith("/openapi.json"):
        return await call_next(request)

    try:
        req_body = await request.body()
    except Exception:
        req_body = b""

    content_type = request.headers.get("Content-Type", "")
    request.state.body = req_body
    request.state.content_type = content_type

    try:
        response = await call_next(request)
    except HTTPException as e:
        log_error(request.url, req_body, content_type, e)
        raise
    except Exception as e:
        log_error(request.url, req_body, content_type, e)
        raise

    # StreamingResponse 등은 감지 후 로깅 생략
    if not hasattr(response, "body_iterator"):
        return response

    res_body = b""
    new_body = []

    try:
        async for chunk in response.body_iterator:
            res_body += chunk
            new_body.append(chunk)
    except Exception as e:
        log_error(request.url, req_body, content_type, e)
        raise

    res_content_type = response.headers.get("Content-Type", "")
    log_level = (
        "info" if 200 <= response.status_code < 300 else "warning" if 400 <= response.status_code < 500 else "error"
    )

    task = BackgroundTask(
        log_info, log_level, request.url, req_body, content_type, response.status_code, res_body, res_content_type
    )

    return Response(
        content=b"".join(new_body),
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.media_type,
        background=task,
    )
