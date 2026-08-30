# flight_alert/schemas/user.py
"""
User Schemas
사용자 관련 요청/응답 스키마
"""

from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def _as_utc(dt: datetime | None) -> datetime | None:
    """DB에는 tzinfo 없는 UTC 시각으로 저장되므로, 응답 직렬화 시
    tzinfo를 명시해 클라이언트가 로컬 시간으로 오인하지 않게 한다."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


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
    email_verified: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    _normalize_created_at = field_validator("created_at")(_as_utc)


class TokenResponse(BaseModel):
    """토큰 응답"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=10)
    new_password: str = Field(..., min_length=8, max_length=72)