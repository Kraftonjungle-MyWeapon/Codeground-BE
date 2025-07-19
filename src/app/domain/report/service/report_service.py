from pathlib import Path
import uuid
from sqlalchemy.orm import Session
from src.app.config.config import settings
from src.app.utils.s3_utils import upload_bytes
from fastapi import UploadFile
from datetime import datetime

from src.app.domain.report.crud import report_crud
from src.app.domain.achievement.service import achievement_service
from src.app.models.models import AchievementTriggerType

ROOT_DIR = Path(__file__).resolve().parents[4]
REPORT_DIR = ROOT_DIR / "resource" / "static" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


async def save_report(
    db: Session, game_id: int | None, reason: str, description: str, video: UploadFile, reported_user_id: int, reporter_user_id: int
) -> None:
    file_name = f"{uuid.uuid4()}.webm"
    env = (getattr(settings, "ENV", None) or getattr(settings, "ENVIRONMENT", None) or "local").lower()
    file_bytes = await video.read()

    # 오늘 날짜 기준 폴더명 생성 (예: '2025-07-08')
    today_str = datetime.now().strftime("%Y-%m-%d")

    if env == "local":
        file_path = REPORT_DIR / file_name
        with open(file_path, "wb") as f:
            f.write(file_bytes)
        video_path = str(file_path)
    else:
        s3_key = f"reports/{today_str}/{file_name}"
        upload_bytes(file_bytes, s3_key, bucket=settings.REPORT_BUCKET)
        video_path = s3_key

    report_crud.create_report(db, game_id, reason, description, video_path, reported_user_id, reporter_user_id)

    # 업적 확인: 신고 횟수
    await achievement_service.handle_achievement_event(
        db,
        reporter_user_id, # 신고를 한 유저의 ID
        AchievementTriggerType.TOTAL_REPORTS_MADE,
    )
