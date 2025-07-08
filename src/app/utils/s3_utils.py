# src/app/utils/s3_utils.py
import boto3
from typing import TypedDict, List
from src.app.models.models import Problem
from src.app.config.config import settings

BUCKET = settings.PROBLEM_BUCKET
REGION = settings.AWS_REGION


class ProblemURLBundle(TypedDict):
    problem_url: str  # JSON 본문 presigned URL
    image_urls: List[str]  # 0-N개 presigned URL, 순서 유지


if not BUCKET or not REGION:
    raise RuntimeError("환경변수 PROBLEM_BUCKET / AWS_REGION 설정이 필요합니다")

ENDTIMER = 300  # 유통기한 타이머
s3 = boto3.client("s3", region_name=REGION)


def sign_s3_url(key: str, ttl: int) -> str:
    if not key:
        raise ValueError("S3 키가 비어 있습니다.")
    try:
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET, "Key": key},
            ExpiresIn=ttl,
        )
        print(f"[DEBUG] presigned URL 생성 성공: key={key}")
        return url
    except Exception as e:
        print(f"[ERROR] presigned URL 생성 실패: key={key}, error={e}")
        raise


async def issue_problem_urls(problem: Problem) -> ProblemURLBundle:
    if problem is None:
        raise ValueError("Problem 객체가 없습니다")

    print(f"[DEBUG] issue_problem_urls: problem_id={problem.problem_id}, body_key={problem.body_key}, image_keys={problem.image_keys}")

    # 문제 본문 URL
    try:
        problem_url = sign_s3_url(problem.body_key, ttl=ENDTIMER)
    except Exception:
        print(f"[ERROR] 문제 {problem.problem_id}의 본문 presigned URL 생성 실패")
        raise

    # 이미지 URL들
    image_urls: list[str] = []

    if not problem.image_keys:
        print(f"[DEBUG] 문제 {problem.problem_id}에 이미지가 없습니다.")
    else:
        for key in problem.image_keys:
            if not key:
                print(f"[WARNING] 문제 {problem.problem_id}에 빈 이미지 key가 포함되어 있습니다. 무시합니다.")
                continue
            try:
                url = sign_s3_url(key, ttl=ENDTIMER)
                image_urls.append(url)
            except Exception:
                print(f"[ERROR] 문제 {problem.problem_id}의 이미지 key={key} presigned URL 생성 실패")
                raise

    return {
        "problem_url": problem_url,
        "image_urls": image_urls,
    }