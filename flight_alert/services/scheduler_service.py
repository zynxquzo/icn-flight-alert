# flight_alert/services/scheduler_service.py
"""
Scheduler Service
APScheduler를 사용한 주기적 비행편 갱신 (Redis 리더 락으로 단일 실행).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from flight_alert.config import get_settings
from flight_alert.infrastructure.redis_client import get_redis
from flight_alert.services.scheduler_leader import try_acquire_leader_lock

logger = logging.getLogger(__name__)

SCHEDULER_LAST_RUN_KEY = "scheduler:refresh_flights:last_run_at"
SCHEDULER_LAST_STATUS_KEY = "scheduler:refresh_flights:last_status"


class FlightScheduler:
    """비행편 자동 갱신 스케줄러"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.is_running = False
        self._interval_minutes = 10
        self._last_run_at: datetime | None = None
        self._last_run_status: str | None = None  # ok | error | skipped

    def get_status(self) -> dict:
        last_at = self._last_run_at
        if last_at and last_at.tzinfo is None:
            last_at = last_at.replace(tzinfo=timezone.utc)
        return {
            "running": self.is_running,
            "interval_minutes": self._interval_minutes,
            "last_run_at": last_at.isoformat() if last_at else None,
            "last_run_status": self._last_run_status,
        }

    def _record_run(self, status: str) -> None:
        self._last_run_at = datetime.now(timezone.utc)
        self._last_run_status = status

    async def _persist_run_metadata(self, status: str) -> None:
        settings = get_settings()
        if not settings.redis_enabled:
            return
        client = await get_redis()
        if client is None:
            return
        now_iso = datetime.now(timezone.utc).isoformat()
        ttl = max(self._interval_minutes * 60 * 24, 3600)
        await client.set(SCHEDULER_LAST_RUN_KEY, now_iso, ex=ttl)
        await client.set(SCHEDULER_LAST_STATUS_KEY, status, ex=ttl)

    async def _refresh_active_flights_async(self) -> None:
        ttl = max(self._interval_minutes * 60 - 30, 60)
        if not await try_acquire_leader_lock(ttl_seconds=ttl):
            logger.info("스케줄러: 다른 인스턴스가 리더 — job 스킵")
            self._record_run("skipped")
            await self._persist_run_metadata("skipped")
            return

        from sqlalchemy import and_, select

        from database import async_session_maker
        from flight_alert.models.flight import Flight
        from flight_alert.services.flight_service import flight_service

        logger.info("========== 비행편 자동 갱신 시작 ==========")

        try:
            async with async_session_maker() as db:
                today = date.today()
                target_start = today
                target_end = today + timedelta(days=2)

                result = await db.scalars(
                    select(Flight).where(
                        and_(
                            Flight.is_active.is_(True),
                            Flight.flight_date >= target_start,
                            Flight.flight_date <= target_end,
                        )
                    )
                )
                active_flights = list(result.all())

                logger.info("갱신 대상 비행편: %s건", len(active_flights))

                success_count = 0
                error_count = 0
                changes_count = 0

                for flight in active_flights:
                    try:
                        res = await flight_service.refresh_flight(db, flight.flight_pk)
                        success_count += 1

                        if res["changes_detected"]:
                            changes_count += 1
                            logger.info(
                                "변경 감지: flight_pk=%s, flight_id=%s, 변경=%s건",
                                flight.flight_pk,
                                flight.flight_id,
                                len(res["changes"]),
                            )

                    except Exception:
                        error_count += 1
                        logger.exception(
                            "갱신 실패: flight_pk=%s, flight_id=%s",
                            flight.flight_pk,
                            flight.flight_id,
                        )

                logger.info(
                    "========== 비행편 자동 갱신 완료 ========== "
                    "대상: %s건, 성공: %s건, 실패: %s건, 변경 감지: %s건",
                    len(active_flights),
                    success_count,
                    error_count,
                    changes_count,
                )
            self._record_run("ok")
            await self._persist_run_metadata("ok")
        except Exception as e:
            logger.exception("스케줄러 실행 중 에러: %s", e)
            self._record_run("error")
            await self._persist_run_metadata("error")

    def start(self, interval_minutes: int = 10):
        """스케줄러 시작"""
        if self.is_running:
            logger.warning("스케줄러가 이미 실행 중입니다")
            return

        self._interval_minutes = interval_minutes
        self.scheduler.add_job(
            func=self._refresh_active_flights_async,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id="refresh_flights_job",
            name="비행편 자동 갱신",
            replace_existing=True,
        )

        self.scheduler.start()
        self.is_running = True

        logger.info("스케줄러 시작됨 (주기: %s분)", interval_minutes)

    def stop(self):
        """스케줄러 중지"""
        if not self.is_running:
            return

        self.scheduler.shutdown()
        self.is_running = False

        logger.info("스케줄러 중지됨")


flight_scheduler = FlightScheduler()
