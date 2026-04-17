# flight_alert/services/auth_service.py
"""
Auth Service
인증 관련 비즈니스 로직
"""

import logging
import os
import threading
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from flight_alert.exceptions import UnauthorizedException
from flight_alert.models.user import User
from flight_alert.repositories.user_repository import user_repository
from flight_alert.schemas.user import UserCreate, UserLogin

load_dotenv()

logger = logging.getLogger(__name__)

SECRET_RAW = os.getenv("JWT_SECRET_KEY")
if not SECRET_RAW or not str(SECRET_RAW).strip():
    raise ValueError("JWT_SECRET_KEY 환경 변수가 설정되지 않았습니다")
SECRET_KEY = str(SECRET_RAW).strip()
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "30"))


def _exp_to_unix_ts(exp: object) -> float:
    if isinstance(exp, (int, float)):
        return float(exp)
    if isinstance(exp, datetime):
        dt = exp
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    return 0.0


class AuthService:
    """인증 서비스"""

    _token_blacklist: dict[str, float] = {}
    _blacklist_lock = threading.Lock()

    def _hash_password(self, password: str) -> str:
        """비밀번호를 bcrypt로 해싱"""
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def _verify_password(self, password: str, hashed: str) -> bool:
        """입력된 비밀번호와 해시된 비밀번호를 비교"""
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))

    def _purge_blacklist_unlocked(self) -> None:
        now = datetime.now(timezone.utc).timestamp()
        dead = [jti for jti, exp_ts in self._token_blacklist.items() if exp_ts <= now]
        for jti in dead:
            del self._token_blacklist[jti]

    def _is_jti_revoked(self, jti: str | None) -> bool:
        if not jti:
            return False
        with self._blacklist_lock:
            self._purge_blacklist_unlocked()
            return jti in self._token_blacklist

    def _add_to_blacklist(self, jti: str, exp_unix: float) -> None:
        with self._blacklist_lock:
            self._purge_blacklist_unlocked()
            self._token_blacklist[jti] = exp_unix

    def signup(self, db: Session, data: UserCreate) -> User:
        """회원가입"""
        existing_user = user_repository.find_by_email(db, data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="이미 등록된 이메일입니다.",
            )

        hashed_password = self._hash_password(data.password)
        new_user = User(email=data.email, password=hashed_password)
        user_repository.save(db, new_user)
        db.commit()

        logger.info("회원가입 완료: %s", data.email)
        return new_user

    def login(self, db: Session, data: UserLogin) -> str:
        """로그인"""
        user = user_repository.find_by_email(db, data.email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="이메일 또는 비밀번호가 올바르지 않습니다.",
            )

        if not self._verify_password(data.password, user.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="이메일 또는 비밀번호가 올바르지 않습니다.",
            )

        access_token = self._create_access_token(user.user_id)
        logger.info("로그인 성공: %s", user.email)
        return access_token

    def _create_access_token(self, user_id: int) -> str:
        """JWT 토큰 생성 (jti 포함, 로그아웃 시 블랙리스트용)"""
        expire = datetime.now(timezone.utc) + timedelta(minutes=EXPIRE_MINUTES)
        jti = str(uuid.uuid4())
        payload = {
            "sub": str(user_id),
            "exp": expire,
            "jti": jti,
        }
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    def get_current_user(self, db: Session, token: str) -> User:
        """토큰으로 현재 사용자 조회"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        except jwt.ExpiredSignatureError:
            raise UnauthorizedException("TOKEN_EXPIRED", "토큰이 만료되었습니다.")
        except jwt.InvalidTokenError:
            raise UnauthorizedException("TOKEN_INVALID", "유효하지 않은 토큰입니다.")

        jti = payload.get("jti")
        if isinstance(jti, str) and self._is_jti_revoked(jti):
            raise UnauthorizedException(
                "TOKEN_REVOKED",
                "로그아웃되었거나 무효화된 토큰입니다.",
            )

        sub = payload.get("sub")
        if sub is None:
            raise UnauthorizedException("TOKEN_INVALID", "유효하지 않은 토큰입니다.")
        try:
            user_id = int(sub)
        except (TypeError, ValueError):
            raise UnauthorizedException("TOKEN_INVALID", "유효하지 않은 토큰입니다.")

        user = user_repository.find_by_id(db, user_id)
        if not user:
            raise UnauthorizedException("TOKEN_INVALID", "사용자를 찾을 수 없습니다.")

        return user

    def logout(self, token: str) -> None:
        """Bearer 토큰을 블랙리스트에 등록 (서명만 유효하면 처리, 만료 토큰은 무시)"""
        try:
            payload = jwt.decode(
                token,
                SECRET_KEY,
                algorithms=[ALGORITHM],
                options={"verify_exp": False},
            )
        except jwt.InvalidTokenError:
            return

        jti = payload.get("jti")
        if not isinstance(jti, str) or not jti:
            return

        exp_unix = _exp_to_unix_ts(payload.get("exp"))
        if exp_unix <= datetime.now(timezone.utc).timestamp():
            return

        self._add_to_blacklist(jti, exp_unix)


auth_service = AuthService()
