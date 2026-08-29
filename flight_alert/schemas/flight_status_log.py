# flight_alert/schemas/flight_status_log.py
"""
FlightStatusLog Schemas
비행편 상태 변경 로그 응답 스키마
"""

from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, field_validator


def _as_utc(dt: datetime | None) -> datetime | None:
    """DB에는 tzinfo 없는 UTC 시각으로 저장되므로, 응답 직렬화 시
    tzinfo를 명시해 클라이언트가 로컬 시간으로 오인하지 않게 한다."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


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

    _normalize_detected_at = field_validator("detected_at")(_as_utc)