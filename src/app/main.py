import uvicorn
import src.app.utils.middlewares.logging_middleware as logging_middleware

from src.app.utils.logging import logger
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from src.app.domain.auth import router as auth_router
from src.app.domain.webrtc import router as webrtc_router
from src.app.domain.match import router as match_router
from src.app.domain.user import router as user_router
from src.app.domain.game import router as game_router
from src.app.domain.analysis import router as analysis_router
from src.app.domain.report import router as report_router
from src.app.domain.problem import router as problem_router
from src.app.config.config import settings
from src.app.domain.match.service.match_service import match_service
from src.app.domain.ranking.router.ranking_controller import router as ranking_router
from src.app.domain.auth.router.github_controller import router as github_router
from src.app.domain.ranking.service.ranking_scheduler import start_ranking_scheduler
from src.app.domain.admin.router.admin_controller import router as admin_router

from src.app.utils.middlewares.domain_limiter import DomainLimiterMiddleware

logger = logger
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "resource" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("--- Server starting up ---")
    match_service.start()  # 백그라운드 매칭 루프 시작
    logger.info("--- Match service started ---")
    start_ranking_scheduler()  # ⬅️ 여기서 스케줄러 시작
    logger.info("--- Ranking scheduler started ---")
    yield
    logger.info("--- Server shutting down ---")
    await match_service.stop()  # 서버 종료 시 안전하게 취소
    logger.info("--- Match service stopped ---")


app = FastAPI(lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    try:
        body = await request.body()
        if "multipart/form-data" in request.headers.get("content-type", ""):
            decoded_body = "[multipart form-data omitted]"
        else:
            decoded_body = body.decode("utf-8") if body else ""
    except Exception:
        decoded_body = "[unreadable body]"

    logger.warning(f"Validation error: {exc}", extra={"request_url": str(request.url), "body": decoded_body})

    return JSONResponse(
        status_code=400,
        content={"detail": exc.errors(), "body": decoded_body},
    )


# 미들웨어 등록
app.add_middleware(DomainLimiterMiddleware)
app.middleware("http")(logging_middleware.log_requests)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,  # 위에서 설정된 도메인
    allow_credentials=True,  # 쿠키 사용 시 반드시 True
    allow_methods=["*"],  # 모든 HTTP 메소드 허용 (또는 필요한 메소드만 설정)
    allow_headers=["*"],  # 모든 헤더 허용 (필요한 헤더만 설정해도 좋음)
)

app.include_router(router=auth_router, prefix=settings.API_V1_STR)
app.include_router(router=github_router, prefix=settings.API_V1_STR)  # ✅ 명확히 분리
app.include_router(router=webrtc_router, prefix=settings.API_V1_STR)
app.include_router(router=match_router, prefix=settings.API_V1_STR)
app.include_router(router=user_router, prefix=settings.API_V1_STR)
app.include_router(router=game_router, prefix=settings.API_V1_STR)
app.include_router(router=ranking_router, prefix=settings.API_V1_STR)
app.include_router(router=analysis_router, prefix=settings.API_V1_STR)
app.include_router(router=report_router, prefix=settings.API_V1_STR)
app.include_router(router=problem_router, prefix=settings.API_V1_STR)
app.include_router(router=admin_router, prefix=settings.API_V1_STR)


@app.get("/")
async def health_check():
    return JSONResponse({"status": "ok"})


# test
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
