"""
JWT jti 블랙리스트 — Redis(수평 확장) 또는 인메모리(단일 인스턴스·테스트).
"""

from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from flight_alert.config import get_settings
from flight_alert.infrastructure.redis_client import get_redis

logger = logging.getLogger(__name__)

BLACKLIST_KEY_PREFIX = "jwt:blacklist:"


def _ttl_seconds(exp_unix: float) -> int:
    remaining = int(exp_unix - datetime.now(timezone.utc).timestamp())
    return max(remaining, 1)


class TokenBlacklistBackend(ABC):
    @abstractmethod
    async def is_revoked(self, jti: str) -> bool: ...

    @abstractmethod
    async def revoke(self, jti: str, exp_unix: float) -> None: ...

    @abstractmethod
    async def clear(self) -> None: ...


class MemoryTokenBlacklist(TokenBlacklistBackend):
    def __init__(self) -> None:
        self._entries: dict[str, float] = {}
        self._lock = threading.Lock()

    def _purge_unlocked(self) -> None:
        now = datetime.now(timezone.utc).timestamp()
        dead = [jti for jti, exp_ts in self._entries.items() if exp_ts <= now]
        for jti in dead:
            del self._entries[jti]

    async def is_revoked(self, jti: str) -> bool:
        with self._lock:
            self._purge_unlocked()
            return jti in self._entries

    async def revoke(self, jti: str, exp_unix: float) -> None:
        with self._lock:
            self._purge_unlocked()
            self._entries[jti] = exp_unix

    async def clear(self) -> None:
        with self._lock:
            self._entries.clear()


class RedisTokenBlacklist(TokenBlacklistBackend):
    async def is_revoked(self, jti: str) -> bool:
        client = await get_redis()
        if client is None:
            return False
        key = f"{BLACKLIST_KEY_PREFIX}{jti}"
        return bool(await client.exists(key))

    async def revoke(self, jti: str, exp_unix: float) -> None:
        client = await get_redis()
        if client is None:
            return
        ttl = _ttl_seconds(exp_unix)
        key = f"{BLACKLIST_KEY_PREFIX}{jti}"
        await client.set(key, "1", ex=ttl)

    async def clear(self) -> None:
        client = await get_redis()
        if client is None:
            return
        cursor = 0
        pattern = f"{BLACKLIST_KEY_PREFIX}*"
        while True:
            cursor, keys = await client.scan(cursor=cursor, match=pattern, count=100)
            if keys:
                await client.delete(*keys)
            if cursor == 0:
                break


class TokenBlacklist:
    """설정에 따라 Redis 또는 메모리 백엔드를 사용합니다."""

    def __init__(self) -> None:
        settings = get_settings()
        if settings.redis_enabled:
            self._backend: TokenBlacklistBackend = RedisTokenBlacklist()
            logger.info("JWT 블랙리스트: Redis (%s)", settings.redis_url)
        else:
            self._backend = MemoryTokenBlacklist()
            logger.warning(
                "JWT 블랙리스트: 인메모리 (REDIS_URL 미설정). "
                "다중 인스턴스 배포 시 REDIS_URL을 설정하세요."
            )

    async def is_revoked(self, jti: str | None) -> bool:
        if not jti:
            return False
        return await self._backend.is_revoked(jti)

    async def revoke(self, jti: str, exp_unix: float) -> None:
        if exp_unix <= datetime.now(timezone.utc).timestamp():
            return
        await self._backend.revoke(jti, exp_unix)

    async def clear(self) -> None:
        await self._backend.clear()


token_blacklist = TokenBlacklist()
