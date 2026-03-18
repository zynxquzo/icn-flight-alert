# flight_alert/services/flight_status_log_service.py

import logging
from sqlalchemy.orm import Session

from flight_alert.repositories.flight_status_log_repository import flight_status_log_repository
from flight_alert.repositories.flight_repository import flight_repository
from flight_alert.schemas.flight_status_log import FlightStatusLogResponse

logger = logging.getLogger(__name__)


class FlightStatusLogService:
    def read_flight_logs(
        self, 
        db: Session, 
        flight_pk: int,
        change_type: str | None = None
    ) -> list[FlightStatusLogResponse]:
        """특정 비행편의 상태 변경 로그 조회"""
        # 비행편 존재 확인
        flight = flight_repository.find_by_id(db, flight_pk)
        if not flight:
            raise ValueError(f"존재하지 않는 비행편입니다. (flight_pk={flight_pk})")
        
        logs = flight_status_log_repository.find_by_flight_pk(db, flight_pk, change_type)
        
        return [
            FlightStatusLogResponse(
                log_id=log.log_id,
                flight_pk=log.flight_pk,
                schedule_date_time=log.schedule_date_time,
                estimated_date_time=log.estimated_date_time,
                terminal_id=log.terminal_id,
                gate_number=log.gate_number,
                remark=log.remark,
                carousel=log.carousel,
                change_type=log.change_type,
                detected_at=log.detected_at,
            )
            for log in logs
        ]


flight_status_log_service = FlightStatusLogService()