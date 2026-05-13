# flight_alert/routers/auth_router.py
"""
Auth Router
인증 관련 API 엔드포인트
"""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from flight_alert.dependencies import get_bearer_token, get_current_user
from flight_alert.models.user import User
from flight_alert.services.auth_service import auth_service
from flight_alert.schemas.user import (
    UserCreate,
    UserResponse,
    TokenResponse,
    UserLogin,
    RefreshTokenRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(data: UserCreate, db: AsyncSession = Depends(get_db)):
    """회원가입

    - 이메일과 비밀번호로 계정 생성
    - SMTP 설정 시 인증 메일 발송
    """
    return await auth_service.signup(db, data)


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    """로그인

    - 액세스 토큰 + 리프레시 토큰 발급
    """
    access_token, refresh_token = await auth_service.login(db, data)
    return {"access_token": access_token, "refresh_token": refresh_token}


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(data: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    """액세스 토큰 재발급 (리프레시 토큰 회전)"""
    access_token, refresh_token = await auth_service.refresh_tokens(db, data.refresh_token)
    return {"access_token": access_token, "refresh_token": refresh_token}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    token: str = Depends(get_bearer_token),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """로그아웃

    - 액세스 토큰 블랙리스트 + 해당 사용자 리프레시 토큰 전부 무효화
    """
    await auth_service.logout(db, token, current_user.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
async def forgot_password(data: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """비밀번호 재설정 요청 (등록된 이메일이면 메일 발송, 응답은 항상 204)"""
    await auth_service.forgot_password(db, data.email)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(data: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """비밀번호 재설정 완료"""
    await auth_service.reset_password(db, data.token, data.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/verify-email")
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    """이메일 인증 (메일 링크, 로그인 불필요)"""
    await auth_service.verify_email_token(db, token)
    return {"detail": "이메일 인증이 완료되었습니다."}


@router.post("/resend-verification", status_code=status.HTTP_204_NO_CONTENT)
async def resend_verification(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """인증 메일 재발송 (로그인 필요)"""
    await auth_service.resend_verification(db, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
