from typing import List
import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_PATH = os.path.join(os.path.dirname(BASE_DIR), ".env")
load_dotenv(ENV_PATH)


class Settings(BaseSettings):
    ENV: str = "local"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = os.environ.get("ENV", "DEV")
    # CORS_ALLOWED_ORIGINS: List[str] = []
    SITE_DOMAIN: str = "codeground"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 14
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "")
    SECRET_KEY_AUTH: str = os.environ.get("SECRET_KEY_AUTH", "")
    DB_HOST: str = os.environ.get("DB_HOST", "")
    DB_USER: str = os.environ.get("DB_USER", "")
    DB_PORT: str = os.environ.get("DB_PORT", "")
    DB_PASSWORD: str = os.environ.get("DB_PASSWORD", "")
    DB_NAME: str = os.environ.get("DB_NAME", "")
    ONLINE_JUDGE_HOST_ENDPOINT: str = os.environ.get("ONLINE_JUDGE_HOST_ENDPOINT", "")
    PROBLEM_BUCKET: str = os.environ.get("PROBLEM_BUCKET", "")
    AWS_REGION: str = os.environ.get("AWS_REGION", "")
    GITHUB_CLIENT_ID: str = os.environ.get("GITHUB_CLIENT_ID", "")
    GITHUB_CLIENT_SECRET: str = os.environ.get("GITHUB_CLIENT_SECRET", "")
    REPORT_BUCKET: str = os.environ.get("REPORT_BUCKET", "")
    PROFILE_IMAGE_BUCKET: str = os.environ.get("PROFILE_IMAGE_BUCKET", "")
    GITHUB_REDIRECT_URL: str

    class Config:
        env_file = ENV_PATH
        env_file_encoding = "utf-8"
        extra = "forbid"

    @property
    def GITHUB_CALLBACK_URL(self) -> str:
        env = (getattr(self, "ENV", None) or getattr(self, "ENVIRONMENT", None) or "local").lower()
        if env in ["local"]:
            return "http://localhost:8000/api/v1/auth/github/callback"
        else:
            return "https://api.code-ground.com/api/v1/auth/github/callback"

    @property
    def FRONTEND_REDIRECT_URL(self) -> str:
        env = (getattr(self, "ENV", None) or getattr(self, "ENVIRONMENT", None) or "local").lower()
        if env in ["local"]:
            return "http://localhost:8080/oauth/callback"
        else:
            return "https://code-ground.com/oauth/callback"

    @property
    def DB_URL(self) -> str:
        return f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def CORS_ALLOWED_ORIGINS(self) -> List[str]:
        # 환경 변수 ENV, ENVIRONMENT 기준으로 개발/운영 환경 판단 (둘 중 하나만 써도 됨)
        env = (getattr(self, "ENV", None) or getattr(self, "ENVIRONMENT", None) or "local").lower()
        if env in ["local"]:
            # 개발환경: 환경변수에서 값을 받아오되 없으면 "*"로 모두 허용
            return ["http://localhost:8080"]
        elif env in ["dev", "DEV"]:
            # 운영/배포환경: 환경변수에서 반드시 허용할 도메인만 리스트로 반환
            raw = os.environ.get("CORS_ALLOWED_ORIGINS", "https://code-ground.com")
            return [o.strip() for o in raw.split(",") if o.strip()]


settings = Settings()
