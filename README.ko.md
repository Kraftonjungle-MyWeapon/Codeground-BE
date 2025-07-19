# Codeground 백엔드

이 저장소는 FastAPI 기반의 백엔드 서비스입니다. 인증 API를 제공하며 데이터베이스 마이그레이션을 위해 SQLAlchemy와 Alembic을 사용합니다.

## 요구 사항

- Python 3.11+
- 의존성 관리를 위한 [Poetry](https://python-poetry.org/)
- PostgreSQL 인스턴스

## 설치

1. **레포지토리 클론**

   ```bash
   git clone <repo-url>
   cd Codeground-Backend
   ```

2. **의존성 설치**

   Poetry로 프로젝트 의존성을 설치합니다:

   ```bash
   poetry install
   ```

3. **환경 변수 설정**

   애플리케이션은 프로젝트 루트 **상위 디렉터리에** 위치한 `.env` 파일에서 변수를 로드합니다. 다음과 같이 `../.env` 파일을 생성합니다:

   ```env
   SECRET_KEY=your-secret-key
   SECRET_KEY_AUTH=your-auth-key
   DB_HOST=localhost
   DB_USER=postgres
   DB_PASSWORD=postgres
   DB_NAME=codeground
   ```

   이 변수들은 PostgreSQL 연결 URL을 구성하는 데 사용됩니다.

4. **데이터베이스 설정**

   Alembic을 사용하여 데이터베이스를 초기화합니다. 마이그레이션 파일이 없다면 생성합니다:

   ```bash
   alembic revision --autogenerate -m "init"
   alembic upgrade head
   ```

## 서비스 실행

Uvicorn으로 FastAPI 애플리케이션을 실행합니다:

```bash
poetry run uvicorn src.app.main:app --reload
```

API는 `http://localhost:8000/`에서 확인할 수 있으며, 인증 엔드포인트는 `/api/v1` 로 시작합니다 (예: `/api/v1/auth/sign-up`).

### WebRTC 시그널링

CodeArena 서비스에서 플레이어들이 음성/영상 통화를 할 수 있도록 WebRTC 시그널링용
WebSocket 엔드포인트를 제공합니다. 다음과 같이 접속합니다.

```text
/api/v1/ws/webrtc/<room>?username=<사용자명>
```

이 소켓으로 전송된 메시지는 같은 방의 다른 참가자들에게 브로드캐스트됩니다.

### WebRTC 테스트 프론트엔드

신호 기능을 간단히 시험해볼 수 있도록 `/static/webrtc_test.html` 경로에 예제 HTML 페이지가 포함되어 있습니다.
백엔드 서버를 실행한 뒤 브라우저에서 다음 주소로 접속하세요:

```bash
poetry run uvicorn src.app.main:app --reload
# 그리고 http://localhost:8000/static/webrtc_test.html 로 접속
```

방 이름과 사용자명을 입력하고 **Join** 버튼을 누르면 연결됩니다.
다른 브라우저나 기기에서 같은 방에 접속하면 화상 채팅을 할 수 있습니다.
페이지는 여러 명의 참가자를 위해 사용자별로 `RTCPeerConnection`을 생성하며,
WebSocket 연결 전에 미디어 스트림을 확보하여 협상 안정성을 높입니다.
페이지가 HTTP인지 HTTPS인지에 따라 스크립트가 `ws://` 또는 `wss://`를 자동으로 선택하고,
참가자가 종료될 때 `leave` 메시지를 브로드캐스트하여 다른 사용자의 피어 연결을 정리합니다.

**주의:** 최근 브라우저들은 평문 `ws://` 연결을 차단하고 있습니다. 로컬호스트가 아니라면 반드시 HTTPS 환경에서 유효한 인증서를 적용하고 `wss://`로 접속해야 합니다.
