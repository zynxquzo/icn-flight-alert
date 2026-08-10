"""
스케줄러 단일 리더 — Redis 분산 락 (SET NX EX).
"""

from __future__ import annotations

import logging
import os
import uuid

from flight_alert.config import get_settings
from flight_alert.infrastructure.redis_client import get_redis

logger = logging.getLogger(__name__)

LEADER_KEY = "scheduler:refresh_flights:leader"
INSTANCE_ID = os.getenv("HOSTNAME") or os.getenv("POD_NAME") or str(uuid.uuid4())[:8]


async def try_acquire_leader_lock(ttl_seconds: int, key: str = LEADER_KEY) -> bool:
    """
    리더 락 획득 시도. REDIS_URL 없거나 SCHEDULER_LEADER_LOCK=false면 항상 True.

    job마다 독립적으로 락을 잡을 수 있도록 key를 지정할 수 있다
    (기본값은 비행편 갱신 job과 공유하는 LEADER_KEY).
    """
    settings = get_settings()
    if not settings.scheduler_leader_lock:
        return True
    if not settings.redis_enabled:
        logger.warning(
            "스케줄러 리더 락: REDIS_URL 미설정 — 모든 인스턴스에서 job이 실행될 수 있습니다."
        )
        return True

    client = await get_redis()
    if client is None:
        return True

    acquired = await client.set(
        key,
        INSTANCE_ID,
        nx=True,
        ex=max(ttl_seconds, 30),
    )
    if acquired:
        logger.debug("스케줄러 리더 락 획득: instance=%s", INSTANCE_ID)
    return bool(acquired)


async def is_current_leader() -> bool:
    """현재 프로세스가 리더인지 (헬스·디버깅용)."""
    settings = get_settings()
    if not settings.redis_enabled:
        return settings.enable_scheduler
    client = await get_redis()
    if client is None:
        return False
    try:
        holder = await client.get(LEADER_KEY)
        return holder == INSTANCE_ID
    except Exception:
        logger.exception("리더 여부 확인 실패")
        return False
