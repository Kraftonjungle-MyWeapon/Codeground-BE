# src/app/utils/s3_utils.py
import boto3
from typing import TypedDict, List
from src.app.models.models import Problem
from src.app.config.config import settings

BUCKET = settings.PROBLEM_BUCKET
REGION = settings.AWS_REGION

class ProblemURLBundle(TypedDict):
    problem_url: str           # JSON 본문 presigned URL
    image_urls : List[str]     # 0-N개 presigned URL, 순서 유지


if not BUCKET or not REGION:
    raise RuntimeError("환경변수 PROBLEM_BUCKET / AWS_REGION 설정이 필요합니다")

ENDTIMER = 300 #유통기한 타이머
s3 = boto3.client("s3", region_name=REGION)



def sign_s3_url(key: str, ttl: int) -> str:
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": key},
        ExpiresIn=ttl,
    )



async def issue_problem_urls(problem : Problem) -> ProblemURLBundle:

    if problem is None:
        raise ValueError("Problem 객체가 없습니다")

    print(f"[DEBUG] issue_problem_urls: {problem.problem_id}, body_key: {problem.body_key}, image_keys: {problem.image_keys}")
    #문제 본문 url
    problem_url = sign_s3_url(problem.body_key, ttl=ENDTIMER)

    #이미지 url
    image_urls: list[str] = []
    if not problem.image_keys:
        print(f"[DEBUG] 문제 {problem.problem_id}에 이미지가 없습니다.")
        return {
            "problem_url": problem_url,
            "image_urls": image_urls
        }
    
    for key in problem.image_keys:                  # TEXT[] 순서를 그대로 유지
        url = sign_s3_url(key, ttl=ENDTIMER)
        image_urls.append(url)

    return {
        "problem_url": problem_url,
        "image_urls": image_urls
    }