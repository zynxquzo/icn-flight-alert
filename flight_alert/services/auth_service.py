# flight_alert/services/auth_service.py
"""
Auth Service
인증 관련 비즈니스 로직
"""

import asyncio
import hashlib
import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from flight_alert.config import get_settings
from flight_alert.exceptions import UnauthorizedException
from flight_alert.models.user import User
from flight_alert.models.user_security_token import SecurityTokenKind
from flight_alert.repositories.token_repository import token_repository
from flight_alert.repositories.user_repository import user_repository
from flight_alert.schemas.user import UserCreate, UserLogin
from flight_alert.services.email_service import email_service
from flight_alert.services.token_blacklist import token_blacklist

logger = logging.getLogger(__name__)

_settings = get_settings()
SECRET_KEY = _settings.jwt_secret_key
ALGORITHM = _settings.jwt_algorithm
EXPIRE_MINUTES = _settings.jwt_expire_minutes
REFRESH_EXPIRE_DAYS = _settings.jwt_refresh_expire_days
EMAIL_VERIFY_HOURS = int(os.getenv("EMAIL_VERIFY_TOKEN_EXPIRE_HOURS", "24"))
PASSWORD_RESET_HOURS = int(os.getenv("PASSWORD_RESET_TOKEN_EXPIRE_HOURS", "1"))
FRONTEND_PUBLIC_URL = _settings.frontend_public_url
REQUIRE_EMAIL_VERIFICATION = _settings.require_email_verification


def _exp_to_unix_ts(exp: object) -> float:
    if isinstance(exp, (int, float)):
        return float(exp)
    if isinstance(exp, datetime):
        dt = exp
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    return 0.0


def _hash_opaque_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _new_opaque_token() -> str:
    return secrets.token_urlsafe(32)


class AuthService:
    """인증 서비스"""

    def _hash_password(self, password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def _verify_password(self, password: str, hashed: str) -> bool:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))

    async def _is_jti_revoked(self, jti: str | None) -> bool:
        return await token_blacklist.is_revoked(jti)

    async def _add_to_blacklist(self, jti: str, exp_unix: float) -> None:
        await token_blacklist.revoke(jti, exp_unix)

    def _create_access_token(self, user_id: int) -> str:
        expire = datetime.now(timezone.utc) + timedelta(minutes=EXPIRE_MINUTES)
        jti = str(uuid.uuid4())
        payload = {
            "sub": str(user_id),
            "exp": expire,
            "jti": jti,
        }
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    async def _issue_refresh(self, db: AsyncSession, user_id: int) -> str:
        raw = _new_opaque_token()
        exp = datetime.utcnow() + timedelta(days=REFRESH_EXPIRE_DAYS)
        await token_repository.add_refresh_token(
            db,
            user_id=user_id,
            token_hash=_hash_opaque_token(raw),
            expires_at=exp,
        )
        return raw

    async def _send_email_verify(self, user: User, db: AsyncSession) -> None:
        await token_repository.delete_security_tokens_of_kind(
            db, user.user_id, SecurityTokenKind.email_verify.value
        )
        raw = _new_opaque_token()
        exp = datetime.utcnow() + timedelta(hours=EMAIL_VERIFY_HOURS)
        await token_repository.add_security_token(
            db,
            user_id=user.user_id,
            kind=SecurityTokenKind.email_verify.value,
            token_hash=_hash_opaque_token(raw),
            expires_at=exp,
        )
        await db.commit()
        link = f"{FRONTEND_PUBLIC_URL}/verify-email?token={raw}"
        subject = "[ICN Flight Alert] 이메일 주소를 확인해 주세요"
        text = f"""안녕하세요.

아래 링크를 눌러 이메일 인증을 완료해 주세요 (약 {EMAIL_VERIFY_HOURS}시간 유효).

{link}

감사합니다.
"""
        html = f'<p>아래 버튼으로 이메일 인증을 완료해 주세요.</p><p><a href="{link}">이메일 인증하기</a></p>'
        await asyncio.to_thread(
            email_service.send_simple_email, user.email, subject, text, html
        )

    async def signup(self, db: AsyncSession, data: UserCreate) -> User:
        existing_user = await user_repository.find_by_email(db, data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="이미 등록된 이메일입니다.",
            )

        hashed_password = self._hash_password(data.password)
        new_user = User(email=data.email, password=hashed_password, email_verified=False)
        await user_repository.save(db, new_user)
        await db.commit()
        await db.refresh(new_user)

        logger.info("회원가입 완료: %s", data.email)
        try:
            await self._send_email_verify(new_user, db)
        except Exception:
            logger.exception("가입 후 인증 메일 발송 실패: %s", data.email)
        return new_user

    async def login(self, db: AsyncSession, data: UserLogin) -> tuple[str, str]:
        user = await user_repository.find_by_email(db, data.email)
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

        if REQUIRE_EMAIL_VERIFICATION and not user.email_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="이메일 인증이 필요합니다. 메일함의 인증 링크를 확인해 주세요.",
            )

        access_token = self._create_access_token(user.user_id)
        refresh_token = await self._issue_refresh(db, user.user_id)
        await db.commit()
        logger.info("로그인 성공: %s", user.email)
        return access_token, refresh_token

    async def refresh_tokens(self, db: AsyncSession, refresh_plain: str) -> tuple[str, str]:
        th = _hash_opaque_token(refresh_plain.strip())
        row = await token_repository.find_valid_refresh_by_hash(db, th)
        if not row:
            raise UnauthorizedException("REFRESH_INVALID", "리프레시 토큰이 유효하지 않습니다.")

        await token_repository.revoke_refresh(db, row.id)
        access = self._create_access_token(row.user_id)
        new_refresh = await self._issue_refresh(db, row.user_id)
        await db.commit()
        return access, new_refresh

    async def get_current_user(self, db: AsyncSession, token: str) -> User:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        except jwt.ExpiredSignatureError:
            raise UnauthorizedException("TOKEN_EXPIRED", "토큰이 만료되었습니다.")
        except jwt.InvalidTokenError:
            raise UnauthorizedException("TOKEN_INVALID", "유효하지 않은 토큰입니다.")

        jti = payload.get("jti")
        if isinstance(jti, str) and await self._is_jti_revoked(jti):
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

        user = await user_repository.find_by_id(db, user_id)
        if not user:
            raise UnauthorizedException("TOKEN_INVALID", "사용자를 찾을 수 없습니다.")

        return user

    async def logout(self, db: AsyncSession, token: str, user_id: int) -> None:
        try:
            payload = jwt.decode(
                token,
                SECRET_KEY,
                algorithms=[ALGORITHM],
                options={"verify_exp": False},
            )
        except jwt.InvalidTokenError:
            pass
        else:
            jti = payload.get("jti")
            if isinstance(jti, str) and jti:
                exp_unix = _exp_to_unix_ts(payload.get("exp"))
                if exp_unix > datetime.now(timezone.utc).timestamp():
                    await self._add_to_blacklist(jti, exp_unix)

        await token_repository.revoke_all_refresh_for_user(db, user_id)
        await db.commit()

    async def logout_blacklist_only(self, token: str) -> None:
        """Bearer만 무효화 (DB 세션 없이 호출할 때)."""
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

        await self._add_to_blacklist(jti, exp_unix)

    async def forgot_password(self, db: AsyncSession, email: str) -> None:
        user = await user_repository.find_by_email(db, email.strip())
        if not user:
            return
        await token_repository.delete_security_tokens_of_kind(
            db, user.user_id, SecurityTokenKind.password_reset.value
        )
        raw = _new_opaque_token()
        exp = datetime.utcnow() + timedelta(hours=PASSWORD_RESET_HOURS)
        await token_repository.add_security_token(
            db,
            user_id=user.user_id,
            kind=SecurityTokenKind.password_reset.value,
            token_hash=_hash_opaque_token(raw),
            expires_at=exp,
        )
        await db.commit()
        link = f"{FRONTEND_PUBLIC_URL}/reset-password?token={raw}"
        subject = "[ICN Flight Alert] 비밀번호 재설정"
        text = f"""비밀번호 재설정을 요청하셨습니다. 아래 링크는 약 {PASSWORD_RESET_HOURS}시간 동안만 유효합니다.

{link}

요청하지 않으셨다면 이 메일은 무시하셔도 됩니다.
"""
        html = f'<p>비밀번호를 재설정하려면 아래 링크를 눌러 주세요.</p><p><a href="{link}">비밀번호 재설정</a></p>'
        await asyncio.to_thread(
            email_service.send_simple_email, user.email, subject, text, html
        )

    async def reset_password(self, db: AsyncSession, token_plain: str, new_password: str) -> None:
        th = _hash_opaque_token(token_plain.strip())
        row = await token_repository.find_valid_security_by_hash(db, th)
        if not row or row.kind != SecurityTokenKind.password_reset.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="유효하지 않거나 만료된 재설정 링크입니다.",
            )
        user = await user_repository.find_by_id(db, row.user_id)
        if not user:
            raise HTTPException(status_code=400, detail="사용자를 찾을 수 없습니다.")

        hashed = self._hash_password(new_password)
        await user_repository.update_password(db, user, hashed)
        await token_repository.mark_security_used(db, row.id)
        await token_repository.revoke_all_refresh_for_user(db, user.user_id)
        await db.commit()

    async def verify_email_token(self, db: AsyncSession, token_plain: str) -> None:
        th = _hash_opaque_token(token_plain.strip())
        row = await token_repository.find_valid_security_by_hash(db, th)
        if not row or row.kind != SecurityTokenKind.email_verify.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="유효하지 않거나 만료된 인증 링크입니다.",
            )
        user = await user_repository.find_by_id(db, row.user_id)
        if not user:
            raise HTTPException(status_code=400, detail="사용자를 찾을 수 없습니다.")

        await user_repository.set_email_verified(db, user, True)
        await token_repository.mark_security_used(db, row.id)
        await db.commit()

    async def resend_verification(self, db: AsyncSession, user: User) -> None:
        if user.email_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="이미 인증된 이메일입니다.",
            )
        await self._send_email_verify(user, db)


auth_service = AuthService()
