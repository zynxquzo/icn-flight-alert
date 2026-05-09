# flight_alert/schemas/user.py
"""
User Schemas
사용자 관련 요청/응답 스키마
"""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    """회원가입 요청"""
    email: EmailStr
    # bcrypt는 입력 비밀번호 바이트가 72를 넘으면 잘라내므로 max_length도 함께 제한
    password: str = Field(..., min_length=8, max_length=72)


class UserLogin(BaseModel):
    """로그인 요청"""
    email: str
    password: str


class UserResponse(BaseModel):
    """사용자 정보 응답"""
    user_id: int
    email: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    """토큰 응답"""
    access_token: str
    token_type: str = "bearer"