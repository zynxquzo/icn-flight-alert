# flight_alert/routers/chatbot_router.py
"""
Chatbot Router
챗봇 관련 API 엔드포인트
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from flight_alert.services.chatbot_service import chatbot_service


router = APIRouter(
    prefix="/chatbot",
    tags=["Chatbot"]
)


class ChatRequest(BaseModel):
    """챗봇 요청"""
    message: str
    terminal: str = "T1"
    wait_time_hours: float | None = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "3시간 기다려야 하는데 뭐하면 좋을까요?",
                "terminal": "T1",
                "wait_time_hours": 3
            }
        }


class ChatResponse(BaseModel):
    """챗봇 응답"""
    message: str
    response: str
    mode: str = Field(
        default="legacy",
        description="legacy | rag | agent",
    )
    sources: list[dict] = Field(
        default_factory=list,
        description="근거로 사용한 문서 doc_id, title, source_url",
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """챗봇과 대화
    
    - 공항에서 할 수 있는 활동 추천
    - 식사, 쇼핑, 휴식 공간 안내
    - 편의시설 정보 제공
    - (RAG) `airport_documents`에 인덱싱된 공항 공식 정보를 검색해 답변
    """
    outcome = await chatbot_service.chat(
        message=request.message,
        terminal=request.terminal,
        wait_time_hours=request.wait_time_hours,
    )

    return ChatResponse(
        message=request.message,
        response=outcome.response,
        mode=outcome.mode,
        sources=outcome.sources,
    )


@router.get("", tags=["Chatbot"])
def chatbot_info():
    """챗봇 서비스 정보"""
    return {
        "service": "인천공항 안내 챗봇",
        "description": "공항 대기 시간 동안 유용한 정보를 제공합니다",
        "features": [
            "식사 장소 추천",
            "쇼핑 정보",
            "휴식 공간 안내",
            "편의시설 정보",
            "RAG(인덱싱된 공항 공식 정보 검색 후 답변, scripts/crawl_and_index.py로 적재)",
            "RAG Agentic(OpenAI function calling: 벡터·키워드 검색·doc 조회 후 답변, 응답에 sources 포함)",
        ],
        "env": {
            "RAG_ENABLED": "기본 true — false로 단순 LLM 안내만 사용",
            "VECTOR_BACKEND": "postgres(기본) 또는 chroma — chroma 시 RAG는 ChromaDB, 나머지 테이블은 PostgreSQL",
            "CHROMA_PERSIST_DIR": "Chroma 저장 경로(기본: 프로젝트/.chroma_airport)",
            "CHROMA_COLLECTION": "컬렉션 이름(기본 airport_documents)",
            "RAG_TOP_K": "단순 RAG 시 벡터 검색 상위 k (기본 5)",
            "RAG_AGENT_ENABLED": "기본 true — 문서가 있으면 도구 호출 에이전트 사용",
            "RAG_AGENT_MODEL": "에이전트 채팅 모델 (기본 gpt-4o-mini)",
            "RAG_AGENT_MAX_ROUNDS": "도구 호출 라운드 상한 (기본 5)",
        },
    }