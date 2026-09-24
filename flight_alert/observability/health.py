"""
확장 헬스 체크 — DB ping, Redis, 스케줄러 마지막 실행.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import text

from database import engine
from flight_alert.config import get_settings
from flight_alert.infrastructure.redis_client import ping_redis
from flight_alert.services.scheduler_leader import is_current_leader
from flight_alert.services.scheduler_service import flight_scheduler

logger = logging.getLogger(__name__)


async def check_database() -> dict:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:
        logger.exception("DB 헬스체크 실패")
        return {"status": "fail", "detail": str(exc)}


async def check_redis() -> dict:
    settings = get_settings()
    if not settings.redis_enabled:
        return {"status": "skipped", "detail": "REDIS_URL not configured"}
    ok = await ping_redis()
    return {"status": "ok" if ok else "fail"}


async def check_scheduler(is_leader: bool) -> dict:
    settings = get_settings()
    info = flight_scheduler.get_status()
    info["enabled"] = settings.enable_scheduler
    info["leader_lock"] = settings.scheduler_leader_lock and settings.redis_enabled
    # 리더가 아닌 인스턴스는 자기 자신의 job을 스킵하므로 last_run_status가 항상
    # "skipped"로 고정된다 — 실제 리더의 실행 결과는 Redis에서 가져와 반영한다.
    if info["leader_lock"] and not is_leader:
        persisted = await flight_scheduler.get_persisted_status()
        if persisted:
            info["last_run_at"] = persisted["last_run_at"]
            info["last_run_status"] = persisted["last_run_status"]
        cleanup_persisted = await flight_scheduler.get_persisted_cleanup_status()
        if cleanup_persisted:
            info["cleanup_last_run_at"] = cleanup_persisted["last_run_at"]
            info["cleanup_last_run_status"] = cleanup_persisted["last_run_status"]
    if settings.enable_scheduler and (
        not info["running"]
        or info["last_run_status"] == "error"
        or info["cleanup_last_run_status"] == "error"
    ):
        info["status"] = "fail"
    else:
        info["status"] = "ok"
    return info


async def build_health_payload() -> dict:
    db_check = await check_database()
    redis_check = await check_redis()

    leader = await is_current_leader()
    scheduler_check = await check_scheduler(leader)
    scheduler_check["is_leader"] = leader

    checks = {
        "database": db_check,
        "redis": redis_check,
        "scheduler": scheduler_check,
    }

    failed = [name for name, c in checks.items() if c.get("status") == "fail"]
    overall = "unhealthy" if failed else "healthy"

    return {
        "status": overall,
        "timestamp": datetime.now(UTC).isoformat(),
        "checks": checks,
    }
