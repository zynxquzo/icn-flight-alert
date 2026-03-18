# flight_alert/repositories/flight_status_log_repository.py

from sqlalchemy.orm import Session
from sqlalchemy import select
from flight_alert.models.flight_status_log import FlightStatusLog


class FlightStatusLogRepository:
    def find_by_flight_pk(
        self, 
        db: Session, 
        flight_pk: int,
        change_type: str | None = None
    ) -> list[FlightStatusLog]:
        """특정 비행편의 상태 변경 로그 조회"""
        stmt = select(FlightStatusLog).where(
            FlightStatusLog.flight_pk == flight_pk
        )
        
        if change_type:
            stmt = stmt.where(FlightStatusLog.change_type == change_type)
        
        stmt = stmt.order_by(FlightStatusLog.detected_at.desc())
        
        result = db.scalars(stmt)
        return result.all()

    def save(self, db: Session, log: FlightStatusLog) -> FlightStatusLog:
        """로그 저장"""
        db.add(log)
        db.flush()
        db.refresh(log)
        return log


flight_status_log_repository = FlightStatusLogRepository()