# flight_alert/routers/auth_router.py
"""
Auth Router
인증 관련 API 엔드포인트
"""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from flight_alert.dependencies import get_bearer_token
from flight_alert.services.auth_service import auth_service
from flight_alert.schemas.user import (
    UserCreate,
    UserResponse,
    TokenResponse,
    UserLogin,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(data: UserCreate, db: AsyncSession = Depends(get_db)):
    """회원가입

    - 이메일과 비밀번호로 계정 생성
    - 이메일 중복 시 409 에러
    """
    return await auth_service.signup(db, data)


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    """로그인

    - 이메일/비밀번호 확인
    - JWT 토큰 발급
    """
    access_token = await auth_service.login(db, data)
    return {"access_token": access_token}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    token: str = Depends(get_bearer_token),
):
    """로그아웃

    - 현재 Bearer 토큰을 서버 블랙리스트에 등록해 만료 전까지 재사용 불가
    - 클라이언트에서는 로컬에 저장한 토큰도 함께 삭제하는 것을 권장
    """
    auth_service.logout(token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
