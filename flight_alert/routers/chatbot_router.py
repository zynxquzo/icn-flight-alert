# flight_alert/routers/chatbot_router.py
"""
Chatbot Router
챗봇 관련 API 엔드포인트
"""

from fastapi import APIRouter
from pydantic import BaseModel

from flight_alert.services.chatbot_service import chatbot_service


router = APIRouter(
    prefix="/chatbot",
    tags=["Chatbot"]
)


class ChatRequest(BaseModel):
    """챗봇 요청"""
    message: str
    terminal: str = "T1"
    wait_time_hours: int | None = None
    
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


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """챗봇과 대화
    
    - 공항에서 할 수 있는 활동 추천
    - 식사, 쇼핑, 휴식 공간 안내
    - 편의시설 정보 제공
    """
    response = chatbot_service.chat(
        message=request.message,
        terminal=request.terminal,
        wait_time_hours=request.wait_time_hours
    )
    
    return ChatResponse(
        message=request.message,
        response=response
    )


@router.get("/", tags=["Chatbot"])
def chatbot_info():
    """챗봇 서비스 정보"""
    return {
        "service": "인천공항 안내 챗봇",
        "description": "공항 대기 시간 동안 유용한 정보를 제공합니다",
        "features": [
            "식사 장소 추천",
            "쇼핑 정보",
            "휴식 공간 안내",
            "편의시설 정보"
        ]
    }