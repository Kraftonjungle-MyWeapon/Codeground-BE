import logging
import sys
import os
import json
from logging.handlers import RotatingFileHandler
from src.app.config.config import settings
from pathlib import Path
from datetime import datetime


# Custom JSON Formatter
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "level": record.levelname,
            "time": datetime.fromtimestamp(record.created).isoformat(timespec="milliseconds") + "Z",
            "module": record.module,
            "line": record.lineno,
            "message": record.getMessage(),
        }

        # Add extra attributes if they exist
        if hasattr(record, "request_url"):
            log_record["request_url"] = record.request_url
        if hasattr(record, "request_body"):
            log_record["request_body"] = record.request_body
        if hasattr(record, "response_body"):
            log_record["response_body"] = record.response_body
        if hasattr(record, "status_code"):
            log_record["status_code"] = record.status_code
        if hasattr(record, "error"):
            log_record["error"] = record.error
        if hasattr(record, "traceback"):
            log_record["traceback"] = record.traceback

        return json.dumps(log_record, ensure_ascii=False)


# 프로젝트 루트 디렉토리 설정
ROOT_DIR = Path(__file__).resolve().parents[3]


def configure_logging():
    try:
        # 로거 인스턴스 생성
        loggers = logging.getLogger("app")
        loggers.setLevel(logging.DEBUG)  # 최소 로그 레벨 설정

        # 기존 핸들러 제거 (중복 로깅 방지)
        if loggers.handlers:
            for handler in loggers.handlers[:]:
                loggers.removeHandler(handler)

        # 핸들러 포맷 설정
        formatter = JsonFormatter()

        # 스트림 핸들러 (콘솔 출력)는 항상 추가
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        if settings.ENVIRONMENT == "PROD":
            stream_handler.setLevel(logging.INFO)
        else:
            stream_handler.setLevel(logging.DEBUG)
        loggers.addHandler(stream_handler)

        # 로컬 환경에서만 파일 핸들러 추가
        if settings.ENVIRONMENT == "local":
            log_dir = ROOT_DIR / "logs"
            os.makedirs(log_dir, exist_ok=True)
            log_file_name = datetime.now().strftime("%Y-%m-%d") + ".log"
            log_file_path = log_dir / log_file_name
            file_handler = RotatingFileHandler(log_file_path, maxBytes=1024 * 1024 * 5, backupCount=5)  # 5MB 파일 5개
            file_handler.setFormatter(formatter)
            file_handler.setLevel(logging.DEBUG) # Local environment should log all debug messages to file
            loggers.addHandler(file_handler)

        return loggers
    except Exception as e:
        print(f"Failed to configure logging: {e}")
        # 로깅 설정 실패 시 기본 로거 반환
        logging.basicConfig(level=logging.INFO)
        return logging.getLogger("app")


logger = configure_logging()
