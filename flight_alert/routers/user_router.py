# flight_alert/routers/user_router.py
"""
User Router
사용자 관련 API 엔드포인트
"""

from fastapi import APIRouter, Depends

from flight_alert.dependencies import get_current_user
from flight_alert.models.user import User
from flight_alert.schemas.user import UserResponse

router = APIRouter(tags=["User"])


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """내 정보 조회
    
    - 로그인 필수
    - JWT 토큰으로 사용자 인증
    """
    return current_user