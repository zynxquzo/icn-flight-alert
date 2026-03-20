# flight_alert/routers/auth_router.py
"""
Auth Router
인증 관련 API 엔드포인트
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from database import get_db
from flight_alert.services.auth_service import auth_service
from flight_alert.schemas.user import (
    UserCreate,
    UserResponse,
    TokenResponse,
    UserLogin,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup(data: UserCreate, db: Session = Depends(get_db)):
    """회원가입
    
    - 이메일과 비밀번호로 계정 생성
    - 이메일 중복 시 409 에러
    """
    return auth_service.signup(db, data)


@router.post("/login", response_model=TokenResponse)
def login(data: UserLogin, db: Session = Depends(get_db)):
    """로그인
    
    - 이메일/비밀번호 확인
    - JWT 토큰 발급
    """
    access_token = auth_service.login(db, data)
    return {"access_token": access_token}