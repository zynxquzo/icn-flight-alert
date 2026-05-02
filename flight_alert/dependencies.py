# flight_alert/dependencies.py
"""
Dependencies
재사용 가능한 FastAPI 의존성
"""

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from flight_alert.exceptions import UnauthorizedException
from flight_alert.models.user import User
from flight_alert.services.auth_service import auth_service

http_bearer = HTTPBearer(auto_error=False)


def get_bearer_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
) -> str:
    """Authorization: Bearer 토큰 문자열 (없으면 TOKEN_MISSING)"""
    if credentials is None or not (credentials.credentials or "").strip():
        raise UnauthorizedException("TOKEN_MISSING", "인증이 필요합니다.")
    return credentials.credentials.strip()


async def get_current_user(
    token: str = Depends(get_bearer_token),
    db: AsyncSession = Depends(get_db),
) -> User:
    """현재 로그인한 사용자 조회"""
    return await auth_service.get_current_user(db, token)
