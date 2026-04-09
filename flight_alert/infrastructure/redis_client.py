"""
Redis 비동기 클라이언트 (싱글톤).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from flight_alert.config import get_settings

if TYPE_CHECKING:
    import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

_client: "aioredis.Redis | None" = None


async def get_redis() -> "aioredis.Redis | None":
    """REDIS_URL이 설정된 경우에만 클라이언트를 반환합니다."""
    global _client
    settings = get_settings()
    if not settings.redis_url:
        return None
    if _client is None:
        import redis.asyncio as aioredis

        _client = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
        )
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def ping_redis() -> bool:
    client = await get_redis()
    if client is None:
        return False
    try:
        return bool(await client.ping())
    except Exception:
        logger.exception("Redis ping 실패")
        return False
