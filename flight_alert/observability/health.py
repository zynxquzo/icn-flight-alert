"""
확장 헬스 체크 — DB ping, Redis, 스케줄러 마지막 실행.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text

from database import engine
from flight_alert.config import get_settings
from flight_alert.infrastructure.redis_client import ping_redis
from flight_alert.services.scheduler_leader import is_current_leader
from flight_alert.services.scheduler_service import flight_scheduler


async def check_database() -> dict:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "fail", "detail": str(exc)}


async def check_redis() -> dict:
    settings = get_settings()
    if not settings.redis_enabled:
        return {"status": "skipped", "detail": "REDIS_URL not configured"}
    ok = await ping_redis()
    return {"status": "ok" if ok else "fail"}


def check_scheduler() -> dict:
    settings = get_settings()
    info = flight_scheduler.get_status()
    info["enabled"] = settings.enable_scheduler
    info["leader_lock"] = settings.scheduler_leader_lock and settings.redis_enabled
    return info


async def build_health_payload() -> dict:
    db_check = await check_database()
    redis_check = await check_redis()
    scheduler_check = check_scheduler()

    leader = False
    if get_settings().redis_enabled and get_settings().scheduler_leader_lock:
        leader = await is_current_leader()
    scheduler_check["is_leader"] = leader

    checks = {
        "database": db_check,
        "redis": redis_check,
        "scheduler": scheduler_check,
    }

    failed = [
        name
        for name, c in checks.items()
        if c.get("status") == "fail"
    ]
    overall = "unhealthy" if failed else "healthy"

    return {
        "status": overall,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }
