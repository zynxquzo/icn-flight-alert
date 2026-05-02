# flight_alert/repositories/flight_status_log_repository.py

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flight_alert.models.flight_status_log import FlightStatusLog


class FlightStatusLogRepository:
    async def find_by_flight_pk(
        self,
        db: AsyncSession,
        flight_pk: int,
        change_type: str | None = None,
    ) -> list[FlightStatusLog]:
        """특정 비행편의 상태 변경 로그 조회"""
        stmt = select(FlightStatusLog).where(FlightStatusLog.flight_pk == flight_pk)

        if change_type:
            stmt = stmt.where(FlightStatusLog.change_type == change_type)

        stmt = stmt.order_by(FlightStatusLog.detected_at.desc())

        result = await db.scalars(stmt)
        return list(result.all())

    async def save(self, db: AsyncSession, log: FlightStatusLog) -> FlightStatusLog:
        """로그 저장"""
        db.add(log)
        await db.flush()
        await db.refresh(log)
        return log


flight_status_log_repository = FlightStatusLogRepository()
