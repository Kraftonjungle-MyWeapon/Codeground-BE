# Refresh Token Rotation (RTR) 시스템 적용 안내 (프론트엔드 개발 가이드)

안녕하세요, 프론트엔드 개발자님. 보안 강화 및 사용자 경험 개선을 위해 Refresh Token Rotation (RTR) 방식의 토큰 관리 시스템이 백엔드에 적용되었습니다.

## 1. 개요

기존에는 Access Token만 사용하여 인증을 관리했지만, 이제 Access Token과 Refresh Token을 함께 사용하여 보안을 강화하고 사용자 편의성을 높였습니다.

-   **Access Token**: 짧은 만료 시간(5분)을 가지며, 실제 API 요청에 사용됩니다.
-   **Refresh Token**: 긴 만료 시간(2주)을 가지며, Access Token이 만료되었을 때 새로운 Access Token을 발급받는 데 사용됩니다. Refresh Token Rotation (RTR) 방식이 적용되어, Refresh Token이 사용될 때마다 새로운 Refresh Token이 발급되고 이전 Refresh Token은 무효화됩니다.

## 2. 핵심 변경 사항

### 2.1. 토큰 발급 및 관리

사용자 로그인 또는 회원가입 시, 백엔드에서 Access Token과 Refresh Token을 모두 발급하여 HTTP Only 쿠키로 클라이언트에 전달합니다.

-   **Access Token**: `access_token` 이라는 이름의 쿠키로 전달됩니다.
-   **Refresh Token**: `refresh_token` 이라는 이름의 쿠키로 전달됩니다.

**쿠키 속성:**

| 속성      | `local` 환경 (개발) | `dev`/`prod` 환경 (운영/배포) |
| --------- | ------------------- | ----------------------------- |
| `secure`  | `False`             | `True` (HTTPS 전용)           |
| `httponly`| `False`             | `True` (JavaScript 접근 불가) |
| `samesite`| `lax`               | `none`                        |
| `domain`  | `None`              | `.code-ground.com`            |
| `max_age` | Access Token: 5분   | Access Token: 5분             |
|           | Refresh Token: 2주  | Refresh Token: 2주            |

**프론트엔드 고려사항:**

-   `httponly` 속성으로 인해 JavaScript에서 `refresh_token` 쿠키에 직접 접근할 수 없습니다. 이는 보안을 위한 의도적인 설계입니다.
-   따라서 `refresh_token`을 사용하여 토큰을 갱신하는 로직은 백엔드와의 통신을 통해 이루어져야 합니다.

### 2.2. 토큰 갱신 (Refresh) API

Access Token이 만료되었을 때 (예: API 요청 시 401 Unauthorized 응답), 다음 엔드포인트를 호출하여 새로운 Access Token과 Refresh Token을 발급받을 수 있습니다.

-   **`POST /api/v1/auth/refresh`**
    -   **설명**: 현재 유효한 `refresh_token`을 사용하여 새로운 `access_token`과 `refresh_token`을 발급받습니다.
    -   **요청**: 별도의 요청 본문 없이, `refresh_token` 쿠키가 자동으로 백엔드로 전송됩니다.
    -   **응답**: 새로운 `access_token`과 `refresh_token`이 HTTP Only 쿠키로 설정되어 반환됩니다. 응답 본문에는 새로운 `access_token`이 포함됩니다.

    ```json
    // POST /api/v1/auth/refresh 응답 예시
    {
      "access_token": "eyJhbGciOiJIUzI1Ni...",
      "token_type": "bearer"
    }
    ```

    **오류 응답:**

    -   `401 Unauthorized`: `refresh_token`이 없거나, 유효하지 않거나, 만료되었거나, 이미 사용된 경우 (RTR 정책에 따라). 이 경우 사용자는 다시 로그인해야 합니다.

### 2.3. 로그아웃

로그아웃 시에는 `access_token`과 `refresh_token` 쿠키를 모두 무효화해야 합니다.

-   **`POST /api/v1/auth/logout`**
    -   **설명**: 서버 측에서 세션을 무효화하고, 클라이언트 측의 `access_token` 및 `refresh_token` 쿠키를 만료시킵니다.
    -   **요청**: 별도의 요청 본문 없이 호출합니다.
    -   **응답**: `{"message": "로그아웃 성공"}`

## 3. 프론트엔드 구현 가이드

### 3.1. 로그인/회원가입 후

-   로그인 또는 회원가입 성공 시, 백엔드에서 `access_token`과 `refresh_token`이 쿠키로 설정되어 전달됩니다. 프론트엔드에서는 별도로 토큰을 저장할 필요 없이, 이후 요청 시 브라우저가 자동으로 쿠키를 포함하여 전송합니다.

### 3.2. Access Token 만료 처리

-   API 요청 시 401 Unauthorized 응답을 받으면, 이는 Access Token이 만료되었을 가능성이 높습니다.
-   이 경우, `POST /api/v1/auth/refresh` 엔드포인트를 호출하여 새로운 토큰을 요청합니다.
-   **성공 시**: 새로운 `access_token`과 `refresh_token`이 쿠키로 설정되므로, 다음 API 요청부터는 새로운 Access Token이 자동으로 사용됩니다.
-   **실패 시 (401 Unauthorized)**: `refresh_token` 또한 유효하지 않거나 만료된 경우이므로, 사용자에게 재로그인을 요청해야 합니다.

**예시 (Axios Interceptor 활용):**

```javascript
import axios from 'axios';

const apiClient = axios.create({
  baseURL: '/api/v1',
  withCredentials: true, // 쿠키를 포함하여 요청을 보냄
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    // Access Token 만료 (401) 이고, refresh 요청이 아닌 경우
    if (error.response.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        // Refresh Token을 사용하여 새로운 Access Token 요청
        await apiClient.post('/auth/refresh');
        // 새로운 Access Token으로 원래 요청 재시도
        return apiClient(originalRequest);
      } catch (refreshError) {
        // Refresh Token도 만료되었거나 유효하지 않은 경우
        console.error('Refresh token expired or invalid. Redirecting to login.', refreshError);
        // 로그인 페이지로 리다이렉트 또는 로그인 모달 표시
        window.location.href = '/login'; // 예시
        return Promise.reject(refreshError);
      }
    }
    return Promise.reject(error);
  }
);

export default apiClient;
```

### 3.3. 로그아웃 처리

-   사용자가 로그아웃 버튼을 클릭하면 `POST /api/v1/auth/logout` 엔드포인트를 호출합니다.
-   이 호출을 통해 서버 측에서 토큰을 무효화하고, 클라이언트 측의 쿠키도 만료됩니다.

## 4. 추가 고려사항

-   **로딩 상태 관리**: 토큰 갱신 중에는 사용자에게 로딩 스피너 등을 보여주어 불필요한 API 요청을 막고 사용자 경험을 개선할 수 있습니다.
-   **동시 요청 처리**: 여러 API 요청이 동시에 401 응답을 반환하여 여러 번의 refresh 요청이 발생하지 않도록, refresh 요청이 진행 중일 때는 다른 요청들을 대기시키고, refresh가 완료된 후 일괄적으로 재시도하는 로직을 구현하는 것이 좋습니다 (위 Axios Interceptor 예시의 `_retry` 플래그 참고).

---

궁금한 점이 있으시면 언제든지 문의해주세요. 감사합니다!