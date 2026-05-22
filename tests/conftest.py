"""pytest 공통 설정 — auth_service import 전 JWT 등 환경 변수 고정."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://test:test@localhost/testdb",
)
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test-secret-key-for-pytest-only-do-not-use-in-production",
)
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("JWT_EXPIRE_MINUTES", "30")
os.environ.setdefault("INCHEON_AIRPORT_API_KEY", "test-api-key")
# 테스트는 인메모리 블랙리스트 (REDIS_URL 미설정)
os.environ.pop("REDIS_URL", None)


@pytest.fixture(autouse=True)
async def _clear_auth_blacklist():
    """테스트 간 JWT 블랙리스트 오염 방지."""
    from flight_alert.services.token_blacklist import token_blacklist

    await token_blacklist.clear()
    yield
    await token_blacklist.clear()
