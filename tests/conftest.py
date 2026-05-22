"""pytest 공통 설정 — auth_service import 전 JWT 등 환경 변수 고정."""

from __future__ import annotations

import os

import pytest

# auth_service 모듈 로드 시 JWT_SECRET_KEY 필수
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test-secret-key-for-pytest-only-do-not-use-in-production",
)
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("JWT_EXPIRE_MINUTES", "30")
os.environ.setdefault("INCHEON_AIRPORT_API_KEY", "test-api-key")


@pytest.fixture(autouse=True)
def _clear_auth_blacklist():
    """테스트 간 JWT 블랙리스트 메모리 오염 방지."""
    from flight_alert.services.auth_service import AuthService

    with AuthService._blacklist_lock:
        AuthService._token_blacklist.clear()
    yield
    with AuthService._blacklist_lock:
        AuthService._token_blacklist.clear()
