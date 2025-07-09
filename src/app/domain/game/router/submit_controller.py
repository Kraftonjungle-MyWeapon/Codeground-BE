from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse, AppStatus
from src.app.domain.game.schemas import game_schemas as schemas
from src.app.domain.game.service import game_service as service
from sqlalchemy.orm import Session
from src.app.core.database import get_db
from src.app.core.security import get_current_user
from src.app.models.models import User

router = APIRouter()


@router.post("/submit")
async def submit_code(request: schemas.SubmitRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    전체 테스트케이스들에 대하여 채점. 전체 정답일 경우 승리 판정하는 로직을 추가해야 할지도?
    """
    AppStatus.should_exit_event = None # 여기서 AppStatus는, EventSourceResponse와 관련된 이벤트 스트리밍 처리에서, 서버 상태나 종료 신호(should_exit_event 등)를 관리하는 데 쓰임.
    # 코드에서 위 값(should_exit_event)을 명시적으로 None으로 리셋하는 이유는, 이전에 남아있던 종료 플래그를 초기화함으로써 새로운 SSE 세션에 영향이 없도록 하기 위함임.
    event_generator = service.stream_evaluate_code(db, current_user.user_id, request.match_id, request.language, request.code, request.problem_id)
    return EventSourceResponse(event_generator)

@router.post("/submit_public")
async def submit_code_public(request: schemas.SubmitRequest):
    """
    visiblity가 public인 테스트케이스들에 대하여 채점.
    """
    AppStatus.should_exit_event = None
    event_generator = service.stream_evaluate_code_public(
        request.language, request.code, request.problem_id
    )
    return EventSourceResponse(event_generator)