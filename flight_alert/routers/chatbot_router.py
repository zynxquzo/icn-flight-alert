# flight_alert/routers/chatbot_router.py
"""챗봇 관련 API 엔드포인트."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from flight_alert.dependencies import get_current_user
from flight_alert.models.user import User
from flight_alert.repositories.chat_repository import chat_repository
from flight_alert.schemas.chat import (
    ChatSessionCreate,
    ChatSessionOut,
    ChatSessionSummary,
    FeedbackOut,
    FeedbackRequest,
    SessionChatRequest,
)
from flight_alert.services.chatbot_service import chatbot_service

router = APIRouter(prefix="/chatbot", tags=["Chatbot"])


# ---------------------------------------------------------------------------
# 하위 호환 단발성 채팅 (세션 없이 즉시 응답)
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str
    terminal: str = "T1"
    wait_time_hours: float | None = None

    class Config:
        json_schema_extra = {
            "example": {
                "message": "3시간 기다려야 하는데 뭐하면 좋을까요?",
                "terminal": "T1",
                "wait_time_hours": 3,
            }
        }


class ChatResponse(BaseModel):
    message: str
    response: str
    mode: str = Field(default="legacy", description="legacy | rag | agent")
    sources: list[dict] = Field(default_factory=list)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """단발성 챗봇 대화 (세션 없이, 하위 호환).

    세션 영속화가 필요하면 `/chatbot/sessions/{id}/messages` 를 사용하세요.
    """
    outcome = await chatbot_service.chat(
        message=request.message,
        terminal=request.terminal,
        wait_time_hours=request.wait_time_hours,
        user_id=current_user.user_id,
    )
    return ChatResponse(
        message=request.message,
        response=outcome.response,
        mode=outcome.mode,
        sources=outcome.sources,
    )


# ---------------------------------------------------------------------------
# 채팅 세션 CRUD
# ---------------------------------------------------------------------------
@router.post(
    "/sessions",
    response_model=ChatSessionOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_session(
    payload: ChatSessionCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    """새 채팅 세션 생성."""
    session = await chat_repository.create_session(
        db, user_id=current_user.user_id, terminal=payload.terminal
    )
    await db.commit()
    await db.refresh(session)
    return ChatSessionOut.model_validate(session)


@router.get("/sessions", response_model=list[ChatSessionSummary])
async def list_sessions(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    """내 채팅 세션 목록 (최근 20개)."""
    sessions = await chat_repository.list_sessions(db, current_user.user_id)
    return [ChatSessionSummary.model_validate(s) for s in sessions]


@router.get("/sessions/{session_id}", response_model=ChatSessionOut)
async def get_session(
    session_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    """특정 세션의 전체 메시지 조회."""
    session = await chat_repository.get_session(db, session_id, current_user.user_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="세션을 찾을 수 없습니다.")
    return ChatSessionOut.model_validate(session)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    """채팅 세션 및 모든 메시지 삭제."""
    deleted = await chat_repository.delete_session(db, session_id, current_user.user_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="세션을 찾을 수 없습니다.")
    await db.commit()


# ---------------------------------------------------------------------------
# 세션 내 메시지 전송 (영속화)
# ---------------------------------------------------------------------------
@router.post("/sessions/{session_id}/messages", response_model=ChatResponse)
async def send_session_message(
    session_id: str,
    request: SessionChatRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    """세션에 메시지를 추가하고 AI 응답을 영속화합니다.

    - RAG 컨텍스트에 등록 비행편·최근 알림이 자동으로 주입됩니다.
    - 응답에 `mode`(legacy/rag/agent)와 `sources`가 포함됩니다.
    """
    session = await chat_repository.get_session(db, session_id, current_user.user_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="세션을 찾을 수 없습니다.")

    outcome = await chatbot_service.chat(
        message=request.message,
        terminal=session.terminal,
        wait_time_hours=request.wait_time_hours,
        user_id=current_user.user_id,
    )

    await chat_repository.add_message(db, session_id, "user", request.message)
    await chat_repository.add_message(
        db,
        session_id,
        "assistant",
        outcome.response,
        mode=outcome.mode,
        sources=outcome.sources,
    )
    if not session.title:
        await chat_repository.update_session_title(db, session_id, request.message[:80])
    await db.commit()

    return ChatResponse(
        message=request.message,
        response=outcome.response,
        mode=outcome.mode,
        sources=outcome.sources,
    )


# ---------------------------------------------------------------------------
# 피드백
# ---------------------------------------------------------------------------
@router.post(
    "/sessions/{session_id}/messages/{message_id}/feedback",
    response_model=FeedbackOut,
)
async def submit_feedback(
    session_id: str,
    message_id: int,
    payload: FeedbackRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    """AI 응답에 helpful / not_helpful 피드백 제출."""
    msg = await chat_repository.set_feedback(
        db,
        message_id=message_id,
        session_id=session_id,
        user_id=current_user.user_id,
        feedback=payload.feedback,
    )
    if not msg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="메시지를 찾을 수 없거나 본인 세션의 AI 응답이 아닙니다.",
        )
    await db.commit()
    return FeedbackOut(message_id=msg.message_id, feedback=msg.feedback)


# ---------------------------------------------------------------------------
# 서비스 정보
# ---------------------------------------------------------------------------
@router.get("")
async def chatbot_info(_: Annotated[User, Depends(get_current_user)]):
    """챗봇 서비스 정보 (로그인 필수)."""
    return {
        "service": "인천공항 안내 챗봇",
        "description": "공항 대기 시간 동안 유용한 정보를 제공합니다",
        "features": [
            "식사 장소 추천",
            "쇼핑 정보",
            "휴식 공간 안내",
            "편의시설 정보",
            "RAG(인덱싱된 공항 공식 정보 검색 후 답변, scripts/crawl_and_index.py로 적재)",
            "RAG Agentic(OpenAI function calling: 벡터·하이브리드·키워드 검색·doc 조회 후 답변)",
            "세션 영속화(POST /chatbot/sessions/{id}/messages)",
            "개인화(등록 비행편·최근 알림 RAG 컨텍스트 자동 주입)",
            "피드백(helpful/not_helpful → 검색 품질 개선)",
        ],
        "env": {
            "RAG_ENABLED": "기본 true — false로 단순 LLM 안내만 사용",
            "VECTOR_BACKEND": "postgres(기본) 또는 chroma",
            "RAG_TOP_K": "단순 RAG 시 벡터 검색 상위 k (기본 5)",
            "RAG_AGENT_ENABLED": "기본 true — 복합 질문에 도구 호출 에이전트 사용",
            "RAG_AGENT_MODEL": "에이전트 채팅 모델 (기본 gpt-4o-mini)",
            "RAG_AGENT_MAX_ROUNDS": "도구 호출 라운드 상한 (기본 5)",
        },
    }
