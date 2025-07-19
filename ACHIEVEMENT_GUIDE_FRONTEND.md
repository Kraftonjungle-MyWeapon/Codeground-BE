# 동적 업적 시스템 개편 안내 (프론트엔드 개발 가이드)

안녕하세요, 프론트엔드 개발자님. 백엔드에서 업적 시스템이 대대적으로 개편되어 관련 내용을 공유해 드립니다.

## 1. 개요

기존 업적 시스템은 새로운 업적을 추가할 때마다 백엔드 코드 수정 및 서버 재배포가 필요했습니다.

**개편된 시스템에서는 관리자가 관리자 페이지를 통해 실시간으로 업적을 생성, 수정, 삭제할 수 있습니다.** 백엔드에서는 유저의 활동(게임 승패, 문제 풀이 등)이 발생할 때마다, 등록된 업적들의 달성 조건을 자동으로 확인하고 유저에게 업적을 부여합니다.

프론트엔드에서는 이 시스템을 활용하여 **(1) 유저에게 획득한 업적 목록을 보여주고**, **(2) 관리자가 업적을 관리할 수 있는 UI를 구현**하는 역할이 필요합니다.

## 2. 핵심 개념

새로운 업적 시스템은 두 가지 핵심 필드로 동작합니다.

-   `trigger_type` (String): 업적 달성의 **조건 종류**를 정의합니다. (예: `TOTAL_WIN`)
-   `parameter` (Integer): 해당 조건의 **달성 목표 값**을 정의합니다. (예: `10`)

**예시:**
관리자가 `trigger_type`을 `TOTAL_WIN`으로, `parameter`를 `10`으로 설정하여 업적을 생성하면, 이는 "총 10승 달성" 업적이 됩니다. 유저가 10번째 승리를 하는 순간, 백엔드에서 자동으로 이 업적을 유저에게 부여합니다.

## 3. API 변경 사항

### 3.1. 유저용 API

유저의 업적 정보를 가져오는 API입니다. **로그인 관련 업적(연속 로그인, 요일별 로그인)은 `GET /api/v1/users/me` API 호출 시점에 체크됩니다.** 게임 종료 후 또는 유저의 업적 페이지에 진입했을 때 호출하여 최신 상태를 반영할 수 있습니다.

-   **`GET /api/v1/achievements/users/{user_id}`**
    -   **설명**: 특정 유저가 획득한 모든 업적 목록을 조회합니다.
    -   **응답**: `UserAchievement` 객체의 리스트를 반환합니다. 각 객체는 달성한 업적의 상세 정보(`achievement` 필드)를 포함하고 있습니다.

    ```json
    // GET /api/v1/achievements/users/1 응답 예시
    [
      {
        "user_achievement_id": 1,
        "user_id": 1,
        "achievement_id": 101,
        "current_value": 1,
        "is_reward_received": false,
        "obtained_at": "2025-07-15T12:00:00Z",
        "achievement": {
          "achievement_id": 101,
          "title": "첫 승리!",
          "description": "첫 번째 승리를 달성하여 실력의 첫걸음을 내딛으세요.",
          "trigger_type": "TOTAL_WIN",
          "parameter": 1,
          "reward_type": "BADGE",
          // ... 기타 업적 정보
        }
      },
      // ... 다른 획득한 업적들
    ]
    ```

-   **`PATCH /api/v1/achievements/users/{user_id}/achievements/{user_achievement_id}/reward-received`**
    -   **설명**: 특정 유저 업적의 `is_reward_received` 상태를 `True`로 업데이트합니다. 이 API는 프론트엔드에서 유저가 보상을 수령했음을 표시할 때 호출되어야 합니다.
    -   **요청 본문 (Request Body):** 없음 (경로 파라미터로 충분)
    -   **응답**: 업데이트된 `UserAchievement` 객체를 반환합니다.
    -   **주의**: `user_id`와 `user_achievement_id`는 URL 경로를 통해 전달됩니다. 이 엔드포인트는 해당 업적이 현재 로그인한 유저의 소유인지, 그리고 보상이 아직 수령되지 않았는지 백엔드에서 검증합니다. 이미 수령된 보상에 대해 다시 호출하면 에러가 발생합니다.
    ```json
    // PATCH /api/v1/achievements/users/1/achievements/101/reward-received 응답 예시
    {
      "user_achievement_id": 101,
      "user_id": 1,
      "achievement_id": 1,
      "current_value": 1,
      "is_reward_received": true,
      "obtained_at": "2025-07-15T12:00:00Z",
      "achievement": {
        "achievement_id": 1,
        "title": "첫 승리!",
        "description": "첫 번째 승리를 달성하여 실력의 첫걸음을 내딛으세요.",
        "trigger_type": "TOTAL_WIN",
        "parameter": 1,
        "reward_type": "BADGE",
        "reward_amount": 1,
        "created_at": "2025-07-15T11:00:00Z",
        "updated_at": "2025-07-15T11:00:00Z"
      }
    }
    ```

-   **`GET /api/v1/achievements/users/{user_id}/all-achievements`**
    -   **설명**: 현재 시스템에 등록된 모든 업적 목록과 특정 유저가 획득한 업적 목록을 함께 조회합니다. 프로필 페이지 등에서 모든 업적 정보를 한 번에 표시할 때 유용합니다.
    -   **응답**: `AllAchievementsResponse` 객체를 반환합니다. 이 객체는 `all_achievements` (모든 업적)와 `user_achievements` (유저가 획득한 업적) 두 필드를 포함합니다.
    ```json
    // GET /api/v1/achievements/users/1/all-achievements 응답 예시
    {
      "all_achievements": [
        {
          "achievement_id": 1,
          "title": "첫 승리!",
          "description": "첫 번째 승리를 달성하여 실력의 첫걸음을 내딛으세요.",
          "trigger_type": "TOTAL_WIN",
          "parameter": 1,
          "reward_type": "BADGE",
          "reward_amount": 1,
          "created_at": "2025-07-15T11:00:00Z",
          "updated_at": "2025-07-15T11:00:00Z"
        },
        // ... 다른 모든 업적들
      ],
      "user_achievements": [
        {
          "user_achievement_id": 101,
          "user_id": 1,
          "achievement_id": 1,
          "current_value": 1,
          "is_reward_received": true,
          "obtained_at": "2025-07-15T12:00:00Z",
          "achievement": {
            "achievement_id": 1,
            "title": "첫 승리!",
            "description": "첫 번째 승리를 달성하여 실력의 첫걸음을 내딛으세요.",
            "trigger_type": "TOTAL_WIN",
            "parameter": 1,
            "reward_type": "BADGE",
            "reward_amount": 1,
            "created_at": "2025-07-15T11:00:00Z",
            "updated_at": "2025-07-15T11:00:00Z"
          }
        },
        // ... 유저가 획득한 업적들
      ]
    }
    ```

### 3.2. 관리자용 API

관리자 페이지에서 업적을 관리(CRUD)하기 위한 API 엔드포인트입니다.

-   **`POST /api/v1/admin/achievements`**
    -   **설명**: 새로운 업적을 생성합니다. **복합 업적을 생성하려면 `prerequisite_achievement_ids` 필드에 선행 업적 ID 목록을 포함합니다.**
    -   **요청 본문 (Request Body):**
        ```json
        {
          "title": "10승 용사",
          "description": "총 10번의 승리를 달성하세요!",
          "trigger_type": "TOTAL_WIN",
          "parameter": 10,
          "reward_type": "BADGE",
          "reward_amount": 1,
          "prerequisite_achievement_ids": [] // 선택 사항: 이 업적을 달성하기 위한 선행 업적 ID 목록
        }
        ```
    -   **복합 업적 예시 (Request Body):**
        ```json
        {
          "title": "마스터 코더",
          "description": "브론즈 승리 업적과 실버 문제 해결 업적을 모두 달성",
          "achievement_category_id": 1,
          "trigger_type": "TOTAL_WIN",
          "parameter": 100,
          "reward_type": "BADGE",
          "reward_amount": 1,
          "prerequisite_achievement_ids": [
            101,  // "브론즈 승리 업적"의 ID (예시)
            102   // "실버 문제 해결 업적"의 ID (예시)
          ]
        }
        ```

-   **`GET /api/v1/admin/achievements`**
    -   **설명**: 현재 시스템에 등록된 모든 업적의 목록을 조회합니다.

-   **`GET /api/v1/admin/achievements/{achievement_id}`**
    -   **설명**: 특정 ID를 가진 업적의 상세 정보를 조회합니다.

-   **`PUT /api/v1/admin/achievements/{achievement_id}`**
    -   **설명**: 기존 업적의 정보를 수정합니다. 요청 본문은 `POST`와 동일합니다.

-   **`DELETE /api/v1/admin/achievements/{achievement_id}`**
    -   **설명**: 특정 업적을 시스템에서 삭제합니다.

## 4. 프론트엔드 구현 가이드

### 4.1. 유저 업적 페이지

-   유저의 프로필이나 별도의 업적 페이지에서 `GET /api/v1/achievements/users/{user_id}/all-achievements` API를 호출하여 모든 업적 정보와 유저가 획득한 업적 정보를 함께 가져옵니다.
-   응답받은 `all_achievements`와 `user_achievements` 데이터를 기반으로 유저가 획득한 업적 목록을 아이콘, 제목, 설명 등과 함께 표시합니다.
-   `obtained_at` 필드를 사용하여 획득 시각을 표시할 수 있습니다.
-   각 `UserAchievement` 객체의 `is_reward_received` 필드를 확인하여 보상 수령 여부를 표시합니다. `False`인 경우 보상 수령 버튼을 활성화하고, `True`인 경우 보상 수령 완료 상태를 표시합니다.

### 4.2. 보상 수령 처리

-   `is_reward_received`가 `False`인 업적에 대해 유저가 보상 수령 버튼을 클릭하면, `PATCH /api/v1/achievements/users/{user_id}/achievements/{user_achievement_id}/reward-received` API를 호출합니다.
-   API 호출 성공 시, 해당 업적의 `is_reward_received` 상태를 `True`로 업데이트하고 UI를 갱신합니다.
-   API 호출 실패 시 (예: 이미 보상을 수령했거나, 권한이 없는 경우), 적절한 에러 메시지를 유저에게 표시합니다.

### 4.3. 게임 종료 후 업적 획득 알림 (선택 사항)

-   게임이 종료되고 결과 페이지로 이동했을 때, `GET /api/v1/achievements/users/{user_id}`를 다시 호출하여 이전 상태와 비교합니다.
-   새롭게 추가된 업적이 있다면, "새로운 업적을 달성했습니다!"와 같은 토스트 메시지나 모달을 띄워 유저에게 즉각적인 피드백을 줄 수 있습니다.

### 4.4. 관리자 페이지 (업적 관리)

-   `3.2. 관리자용 API`를 사용하여 업적을 생성, 조회, 수정, 삭제할 수 있는 UI를 구현합니다.
-   **업적 생성/수정 폼**에는 다음 필드들이 포함되어야 합니다.
    -   `title` (text input)
    -   `description` (textarea)
    -   `trigger_type` (select/dropdown)
    -   `parameter` (number input)
    -   `reward_type` (select/dropdown)
    -   `reward_amount` (number input)
-   `trigger_type`과 `reward_type` 필드는 아래 `5. 사용 가능한 trigger_type 목록`을 참고하여 옵션을 구성해주세요.

## 5. 사용 가능한 `trigger_type` 목록

관리자가 업적을 생성할 때 선택할 수 있는 `trigger_type`의 전체 목록입니다.

| `trigger_type` 값            | 설명                                                     | `parameter` 의미             |
| ---------------------------- | -------------------------------------------------------- | ---------------------------- |
| `TOTAL_WIN`                  | 총 승리 횟수                                             | 목표 승리 횟수               |
| `FIRST_WIN`                  | 첫 승리 (parameter는 1로 설정 권장)                      | 목표 승리 횟수 (1)           |
| `CONSECUTIVE_WIN`            | 현재 연속 승리 횟수                                      | 목표 연승 횟수               |
| `TOTAL_LOSS`                 | 총 패배 횟수                                             | 목표 패배 횟수               |
| `CONSECUTIVE_LOSS`           | 현재 연속 패배 횟수                                      | 목표 연패 횟수               |
| `TOTAL_DRAW`                 | 총 무승부 횟수                                           | 목표 무승부 횟수             |
| `PROBLEM_SOLVED`             | 승리한 고유한 문제의 총개수                              | 목표 문제 풀이 개수          |
| `WIN_WITHIN_N_SUBMISSIONS`   | 특정 횟수 **이하**로 코드를 제출하여 승리                | 최대 제출 횟수 (이하)        |
| `WIN_WITHOUT_MISS`           | 오답 제출 없이 승리 (parameter는 1로 설정 권장)          | 최대 제출 횟수 (1)           |
| `FAST_WIN`                   | 특정 시간(초) 이내에 승리                                | 목표 시간(초) (이하)         |
| `APPROVED_PROBLEM_COUNT`     | 유저가 등록한 문제가 관리자에 의해 승인된 횟수           | 목표 승인 횟수               |
| `CONSECUTIVE_LOGIN`          | 연속 로그인 일수                                         | 목표 연속 로그인 일수        |
| `LOGIN_ON_DAY_OF_WEEK`       | 특정 요일에 로그인                                       | 요일 (0=월요일, 6=일요일)    |
| `TOTAL_REPORTS_MADE`         | 총 신고 횟수 (유저가 다른 유저를 신고한 횟수)            | 목표 신고 횟수               |

---

궁금한 점이 있으시면 언제든지 문의해주세요. 감사합니다!