# flight_alert/schemas/user.py
"""
User Schemas
사용자 관련 요청/응답 스키마
"""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr


class UserCreate(BaseModel):
    """회원가입 요청"""
    email: EmailStr
    password: str


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