# 문제 관리 시스템 개편 안내 (프론트엔드 개발 가이드)

안녕하세요, 프론트엔드 개발자님. 백엔드에서 문제 관리 시스템이 개편되어 관련 내용을 공유해 드립니다.

## 1. 개요

기존 문제 관리 시스템은 제한적인 기능만을 제공했습니다. 개편된 시스템에서는 관리자가 관리자 페이지를 통해 등록된 문제들을 실시간으로 조회, 수정, 삭제할 수 있습니다.

**개편된 시스템에서는 관리자가 관리자 페이지를 통해 문제의 DB 정보(제목, 난이도 등)와 S3에 저장된 실제 문제 본문 및 이미지 파일을 함께 관리할 수 있습니다.**

프론트엔드에서는 이 시스템을 활용하여 **(1) 모든 문제 목록을 보여주고**, **(2) 특정 문제의 상세 정보를 조회하며**, **(3) 문제의 DB 정보와 S3 파일을 수정하고**, **(4) 문제를 삭제할 수 있는 UI를 구현**하는 역할이 필요합니다.

## 2. 핵심 개념

문제는 크게 두 가지 유형의 정보로 구성됩니다.

-   **DB 정보**: 문제의 제목, 난이도, 카테고리, 언어, 승인 여부 등 구조화된 데이터입니다. (`Problem` 모델)
-   **S3 파일**: 문제의 실제 본문 내용(JSON 파일)과 문제 설명에 사용되는 이미지 파일들입니다. 이들은 S3 버킷에 저장되며, `body_key`와 `image_keys`를 통해 참조됩니다.

관리자 페이지에서 문제를 수정할 때, DB 정보와 S3 파일 정보를 동시에 업데이트할 수 있도록 API가 설계되었습니다.

## 3. API 변경 사항 (관리자용)

관리자 페이지에서 문제를 관리(CRUD)하기 위한 API 엔드포인트입니다.

### 3.1. 모든 문제 목록 조회

-   **`GET /api/v1/admin/problems`**
    -   **설명**: 현재 시스템에 등록된 모든 문제의 목록을 조회합니다.
    -   **응답**: `AdminProblemOut` 객체의 리스트를 반환합니다.

    ```json
    // GET /api/v1/admin/problems 응답 예시
    [
      {
        "problem_id": 1,
        "title": "두 수의 합",
        "difficulty": "bronze",
        "is_approved": true,
        "created_at": "2025-07-16T10:00:00Z",
        "author_id": 10,
        "category": ["수학", "구현"],
        "language": ["python3", "java"]
      },
      // ... 다른 문제들
    ]
    ```

### 3.2. 특정 문제 상세 조회

-   **`GET /api/v1/admin/problems/{problem_id}`**
    -   **설명**: 특정 ID를 가진 문제의 상세 정보를 조회합니다. DB 정보와 함께 S3에 저장된 문제 본문 및 이미지 파일에 접근할 수 있는 Pre-signed URL을 반환합니다.
    -   **응답**: `AdminProblemDetailOut` 객체를 반환합니다.

    ```json
    // GET /api/v1/admin/problems/1 응답 예시
    {
      "problem_id": 1,
      "title": "두 수의 합",
      "difficulty": "bronze",
      "is_approved": true,
      "created_at": "2025-07-16T10:00:00Z",
      "author_id": 10,
      "category": ["수학", "구현"],
      "language": ["python3", "java"],
      "problem_url": "https://your-s3-bucket.s3.amazonaws.com/problems/1/body.json?AWSAccessKeyId=...",
      "image_urls": [
        "https://your-s3-bucket.s3.amazonaws.com/problems/1/image1.png?AWSAccessKeyId=...",
        "https://your-s3-bucket.s3.amazonaws.com/problems/1/image2.png?AWSAccessKeyId=..."
      ],
      "problem_prefix": "def solution(a, b):\n    return a + b",
      "testcase_prefix": "[1, 2]\n[3, 4]"
    }
    ```

### 3.3. 특정 문제 수정

-   **`PUT /api/v1/admin/problems/{problem_id}`**
    -   **설명**: 기존 문제의 DB 정보와 S3 파일 내용을 수정합니다. `multipart/form-data` 형식으로 요청을 보냅니다.
    -   **요청 본문 (Request Body):**
        -   `problem_update`: `AdminProblemUpdate` 스키마에 해당하는 JSON 문자열 (Form Field로 전송)
        -   `problem_body_file`: 문제 본문 파일 (Optional, File Field로 전송)
        -   `image_files`: 이미지 파일 목록 (Optional, File Field로 전송, 배열)

    ```http
    PUT /api/v1/admin/problems/1
    Content-Type: multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW

    ------WebKitFormBoundary7MA4YWxkTrZu0gW
    Content-Disposition: form-data; name="problem_update"

    {
      "title": "두 수의 합 (수정됨)",
      "difficulty": "silver",
      "category": ["수학", "알고리즘"],
      "is_approved": true
    }
    ------WebKitFormBoundary7MA4YWxkTrZu0gW
    Content-Disposition: form-data; name="problem_body_file"; filename="body.json"
    Content-Type: application/json

    { "description": "새로운 문제 설명입니다." }
    ------WebKitFormBoundary7MA4YWxkTrZu0gW
    Content-Disposition: form-data; name="image_files"; filename="new_image.png"
    Content-Type: image/png

    <binary content of new_image.png>
    ------WebKitFormBoundary7MA4YWxkTrZu0gW--
    ```

    -   **응답**: 업데이트된 `AdminProblemOut` 객체를 반환합니다.
    -   **주의**: `problem_update`는 JSON 문자열로 직렬화하여 `Form` 필드로 보내야 합니다. 파일들은 `File` 필드로 보냅니다. 기존 `image_keys`에 해당하는 파일만 업데이트되며, 새로운 이미지를 추가하려면 백엔드 로직 수정이 필요할 수 있습니다.

### 3.4. 특정 문제 삭제

-   **`DELETE /api/v1/admin/problems/{problem_id}`**
    -   **설명**: 특정 ID를 가진 문제를 시스템에서 삭제합니다. 이 때, 해당 문제와 연관된 `Match` 및 `MatchLog` 기록의 `problem_id`는 `NULL`로 설정됩니다.
    -   **응답**: 성공 시 204 No Content (응답 본문 없음), 실패 시 404 Not Found.

## 4. 프론트엔드 구현 가이드

### 4.1. 문제 목록 페이지

-   `GET /api/v1/admin/problems` API를 호출하여 모든 문제 목록을 가져옵니다.
-   응답받은 데이터를 기반으로 문제 목록을 테이블 형태로 표시합니다. 각 문제의 제목, 난이도, 승인 여부, 작성자, 카테고리, 언어 등을 보여줄 수 있습니다.
-   각 문제 항목에 상세 보기, 수정, 삭제 버튼을 추가합니다.

### 4.2. 문제 상세/수정 페이지

-   **상세 보기**: 문제 목록에서 특정 문제를 선택하면 `GET /api/v1/admin/problems/{problem_id}` API를 호출하여 상세 정보를 가져옵니다.
    -   `problem_url`을 사용하여 문제 본문 JSON 파일을 가져와 파싱하고 내용을 표시합니다.
    -   `image_urls`를 사용하여 문제 설명에 포함된 이미지들을 표시합니다.
    -   `problem_prefix`와 `testcase_prefix`도 함께 표시합니다.
-   **수정**: 상세 보기 페이지에서 수정 모드로 전환하거나, 별도의 수정 페이지로 이동합니다.
    -   `PUT /api/v1/admin/problems/{problem_id}` API를 사용하여 문제 정보를 업데이트합니다.
    -   DB 필드(`title`, `difficulty`, `category`, `language`, `is_approved`, `problem_prefix`, `testcase_prefix`)는 폼 입력 필드와 바인딩합니다.
    -   문제 본문 파일(`problem_body_file`)과 이미지 파일(`image_files`)은 파일 업로드 컴포넌트를 통해 사용자가 새로운 파일을 선택할 수 있도록 합니다. 사용자가 파일을 선택하지 않으면 기존 파일은 유지됩니다.
    -   요청 시 `problem_update` 필드는 JSON 객체를 문자열로 변환하여 `multipart/form-data`의 일반 필드로 전송해야 합니다.

### 4.3. 문제 삭제

-   문제 목록 또는 상세 페이지에서 삭제 버튼을 클릭하면 `DELETE /api/v1/admin/problems/{problem_id}` API를 호출합니다.
-   삭제 전 사용자에게 확인 메시지를 표시하는 것이 좋습니다.
-   API 호출 성공 시, 목록에서 해당 문제를 제거하고 성공 메시지를 표시합니다.

---

궁금한 점이 있으시면 언제든지 문의해주세요. 감사합니다!