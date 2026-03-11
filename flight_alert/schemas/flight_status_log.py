# flight_alert/schemas/flight_status_log.py
"""
FlightStatusLog Schemas
비행편 상태 변경 로그 응답 스키마
"""

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class FlightStatusLogResponse(BaseModel):
    """비행편 상태 로그 응답"""
    log_id: int
    flight_pk: int
    schedule_date_time: str | None
    estimated_date_time: str | None
    terminal_id: str | None
    gate_number: str | None
    remark: str | None
    carousel: str | None
    change_type: str | None
    detected_at: datetime

    model_config = ConfigDict(from_attributes=True)