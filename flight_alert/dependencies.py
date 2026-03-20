# flight_alert/dependencies.py
"""
Dependencies
재사용 가능한 FastAPI 의존성
"""

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from database import get_db
from flight_alert.services.auth_service import auth_service
from flight_alert.models.user import User

# Authorization 헤더에서 Bearer 토큰을 자동으로 추출
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """현재 로그인한 사용자 조회"""
    return auth_service.get_current_user(db, token)