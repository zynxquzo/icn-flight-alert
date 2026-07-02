# flight_alert/repositories/token_repository.py
"""리프레시 토큰·보안(인증·재설정) 토큰 저장소."""

from datetime import datetime, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from flight_alert.models.refresh_token import RefreshToken
from flight_alert.models.user_security_token import UserSecurityToken


class TokenRepository:
    async def add_refresh_token(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        token_hash: str,
        expires_at: datetime,
    ) -> RefreshToken:
        row = RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        db.add(row)
        await db.flush()
        await db.refresh(row)
        return row

    async def find_valid_refresh_by_hash(
        self, db: AsyncSession, token_hash: str
    ) -> RefreshToken | None:
        now = datetime.now(timezone.utc)
        stmt = (
            select(RefreshToken)
            .where(RefreshToken.token_hash == token_hash)
            .where(RefreshToken.revoked_at.is_(None))
            .where(RefreshToken.expires_at > now)
        )
        return await db.scalar(stmt)

    async def revoke_refresh(self, db: AsyncSession, token_id: int) -> None:
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.id == token_id)
            .values(revoked_at=datetime.now(timezone.utc))
        )

    async def revoke_all_refresh_for_user(self, db: AsyncSession, user_id: int) -> None:
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id)
            .where(RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )

    async def add_security_token(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        kind: str,
        token_hash: str,
        expires_at: datetime,
    ) -> UserSecurityToken:
        row = UserSecurityToken(
            user_id=user_id,
            kind=kind,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        db.add(row)
        await db.flush()
        await db.refresh(row)
        return row

    async def delete_security_tokens_of_kind(
        self, db: AsyncSession, user_id: int, kind: str
    ) -> None:
        await db.execute(
            delete(UserSecurityToken).where(
                UserSecurityToken.user_id == user_id,
                UserSecurityToken.kind == kind,
            )
        )

    async def find_valid_security_by_hash(
        self, db: AsyncSession, token_hash: str
    ) -> UserSecurityToken | None:
        now = datetime.now(timezone.utc)
        stmt = (
            select(UserSecurityToken)
            .where(UserSecurityToken.token_hash == token_hash)
            .where(UserSecurityToken.used_at.is_(None))
            .where(UserSecurityToken.expires_at > now)
        )
        return await db.scalar(stmt)

    async def mark_security_used(self, db: AsyncSession, token_id: int) -> None:
        await db.execute(
            update(UserSecurityToken)
            .where(UserSecurityToken.id == token_id)
            .values(used_at=datetime.now(timezone.utc))
        )


token_repository = TokenRepository()
