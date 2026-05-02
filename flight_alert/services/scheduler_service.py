# flight_alert/services/scheduler_service.py
"""
Scheduler Service
APScheduler를 사용한 주기적 비행편 갱신
"""

import asyncio
import logging
from datetime import date, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


class FlightScheduler:
    """비행편 자동 갱신 스케줄러"""

    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.is_running = False

    def refresh_active_flights(self) -> None:
        """활성화된 비행편 자동 갱신 (백그라운드 스레드에서 asyncio 이벤트 루프 실행)"""
        asyncio.run(self._refresh_active_flights_async())

    async def _refresh_active_flights_async(self) -> None:
        from sqlalchemy import and_, select

        from database import async_session_maker
        from flight_alert.models.flight import Flight
        from flight_alert.services.flight_service import flight_service

        logger.info("========== 비행편 자동 갱신 시작 ==========")

        async with async_session_maker() as db:
            try:
                today = date.today()
                target_start = today
                target_end = today + timedelta(days=2)

                result = await db.scalars(
                    select(Flight).where(
                        and_(
                            Flight.is_active == True,  # noqa: E712
                            Flight.flight_date >= target_start,
                            Flight.flight_date <= target_end,
                        )
                    )
                )
                active_flights = list(result.all())

                logger.info(f"갱신 대상 비행편: {len(active_flights)}건")

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
                                "✅ 변경 감지: flight_pk=%s, flight_id=%s, 변경=%s건",
                                flight.flight_pk,
                                flight.flight_id,
                                len(res["changes"]),
                            )

                    except Exception as e:
                        error_count += 1
                        logger.error(
                            "❌ 갱신 실패: flight_pk=%s, flight_id=%s, error=%s",
                            flight.flight_pk,
                            flight.flight_id,
                            e,
                        )

                logger.info(
                    "========== 비행편 자동 갱신 완료 ==========\n"
                    f"대상: {len(active_flights)}건, "
                    f"성공: {success_count}건, "
                    f"실패: {error_count}건, "
                    f"변경 감지: {changes_count}건"
                )

            except Exception as e:
                logger.error(f"스케줄러 실행 중 에러: {e}")

    def start(self, interval_minutes: int = 10):
        """스케줄러 시작

        Args:
            interval_minutes: 갱신 주기 (분 단위, 기본 10분)
        """
        if self.is_running:
            logger.warning("스케줄러가 이미 실행 중입니다")
            return

        self.scheduler.add_job(
            func=self.refresh_active_flights,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id="refresh_flights_job",
            name="비행편 자동 갱신",
            replace_existing=True,
        )

        self.scheduler.start()
        self.is_running = True

        logger.info(f"✅ 스케줄러 시작됨 (주기: {interval_minutes}분)")

    def stop(self):
        """스케줄러 중지"""
        if not self.is_running:
            logger.warning("스케줄러가 실행 중이 아닙니다")
            return

        self.scheduler.shutdown()
        self.is_running = False

        logger.info("⏹️ 스케줄러 중지됨")


flight_scheduler = FlightScheduler()
