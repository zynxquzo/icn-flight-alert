"""인증 서비스: JWT 블랙리스트·리프레시 회전 단위 테스트."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest

from flight_alert.exceptions import UnauthorizedException
from flight_alert.services.auth_service import (
    ALGORITHM,
    SECRET_KEY,
    AuthService,
    auth_service,
)


@pytest.fixture
def svc() -> AuthService:
    return AuthService()


class TestJwtBlacklist:
    @pytest.mark.asyncio
    async def test_revoked_jti_detected(self, svc: AuthService):
        exp = datetime.now(timezone.utc).timestamp() + 3600
        await svc._add_to_blacklist("jti-abc", exp)
        assert await svc._is_jti_revoked("jti-abc") is True
        assert await svc._is_jti_revoked("jti-other") is False

    @pytest.mark.asyncio
    async def test_expired_jti_purged(self, svc: AuthService):
        past = datetime.now(timezone.utc).timestamp() - 10
        await svc._add_to_blacklist("jti-old", past)
        assert await svc._is_jti_revoked("jti-old") is False

    @pytest.mark.asyncio
    async def test_logout_blacklist_only(self, svc: AuthService):
        token = jwt.encode(
            {
                "sub": "1",
                "jti": "logout-jti",
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            },
            SECRET_KEY,
            algorithm=ALGORITHM,
        )
        await svc.logout_blacklist_only(token)
        assert await svc._is_jti_revoked("logout-jti") is True


@pytest.mark.asyncio
async def test_refresh_tokens_rotates_and_issues_new_pair():
    mock_db = AsyncMock()
    row = MagicMock()
    row.id = 10
    row.user_id = 42

    with (
        patch(
            "flight_alert.services.auth_service.token_repository.find_valid_refresh_by_hash",
            new_callable=AsyncMock,
            return_value=row,
        ) as mock_find,
        patch(
            "flight_alert.services.auth_service.token_repository.revoke_refresh",
            new_callable=AsyncMock,
        ) as mock_revoke,
        patch(
            "flight_alert.services.auth_service.token_repository.add_refresh_token",
            new_callable=AsyncMock,
        ) as mock_add,
    ):
        access, refresh = await auth_service.refresh_tokens(mock_db, "plain-refresh-token")

    mock_find.assert_awaited_once()
    mock_revoke.assert_awaited_once_with(mock_db, 10)
    mock_add.assert_awaited_once()
    assert isinstance(access, str) and access
    assert isinstance(refresh, str) and refresh
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_refresh_tokens_invalid_raises():
    mock_db = AsyncMock()
    with patch(
        "flight_alert.services.auth_service.token_repository.find_valid_refresh_by_hash",
        new_callable=AsyncMock,
        return_value=None,
    ):
        with pytest.raises(UnauthorizedException) as exc_info:
            await auth_service.refresh_tokens(mock_db, "bad-token")
    assert exc_info.value.code == "REFRESH_INVALID"


@pytest.mark.asyncio
async def test_get_current_user_rejects_blacklisted_jti(svc: AuthService):
    mock_db = AsyncMock()
    jti = "blocked-jti"
    token = jwt.encode(
        {
            "sub": "1",
            "jti": jti,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    await svc._add_to_blacklist(jti, datetime.now(timezone.utc).timestamp() + 3600)

    with pytest.raises(UnauthorizedException) as exc_info:
        await svc.get_current_user(mock_db, token)
    assert exc_info.value.code == "TOKEN_REVOKED"


@pytest.mark.asyncio
async def test_get_current_user_valid_token():
    mock_db = AsyncMock()
    user = MagicMock()
    user.user_id = 1
    user.email = "u@example.com"

    token = auth_service._create_access_token(1)

    with patch(
        "flight_alert.services.auth_service.user_repository.find_by_id",
        new_callable=AsyncMock,
        return_value=user,
    ):
        result = await auth_service.get_current_user(mock_db, token)

    assert result is user
