# src/app/utils/s3_utils.py
import boto3
from typing import TypedDict, List
from src.app.models.models import Problem
from src.app.config.config import settings

PROBLEM_BUCKET = settings.PROBLEM_BUCKET
REGION = settings.AWS_REGION
REPORT_BUCKET = settings.REPORT_BUCKET


class ProblemURLBundle(TypedDict):
    problem_url: str  # JSON 본문 presigned URL
    image_urls: List[str]  # 0-N개 presigned URL, 순서 유지


# if not PROBLEM_BUCKET or not REGION:
#     raise RuntimeError("환경변수 PROBLEM_BUCKET / AWS_REGION 설정이 필요합니다")

ENDTIMER = 3600  # presigned URL TTL (초)

# IAM Task Role을 사용하는 ECS 환경에선 Access Key 불필요
s3 = boto3.client("s3", region_name=REGION)


def sign_s3_url(key: str, ttl: int) -> str:
    try:
        return s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": PROBLEM_BUCKET, "Key": key},
            ExpiresIn=ttl,
        )
    except Exception as e:
        pass
        # raise RuntimeError(f"Presigned URL 생성 실패: {key}, 에러: {e}")


def upload_bytes(data: bytes, key: str, bucket: str = REPORT_BUCKET) -> None:
    try:
        s3.put_object(Bucket=bucket, Key=key, Body=data)
    except Exception as e:
        raise RuntimeError(f"S3 업로드 실패: {key}, 에러: {e}")


async def issue_problem_urls(problem: Problem) -> ProblemURLBundle:
    if problem is None:
        pass
        # raise ValueError("Problem 객체가 없습니다")

    print(
        f"[DEBUG] issue_problem_urls: problem_id={problem.problem_id}, body_key={problem.body_key}, image_keys={problem.image_keys}")

    # 문제 본문 URL 생성
    problem_url = sign_s3_url(problem.body_key, ttl=ENDTIMER)

    # 이미지 URL 리스트 생성
    image_urls: List[str] = []
    if problem.image_keys:
        for key in problem.image_keys:
            try:
                image_url = sign_s3_url(key, ttl=ENDTIMER)
                image_urls.append(image_url)
            except Exception as e:
                pass
            #     print(f"[WARNING] presigned URL 생성 실패 (image key: {key}): {e}")
    else:
        print(f"[DEBUG] 문제 {problem.problem_id}에 이미지가 없습니다.")

    return {
        "problem_url": problem_url,
        "image_urls": image_urls
    }
