# flight_alert/schemas/notification.py
"""
Notification Schemas
알림 관련 응답 스키마
"""

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, field_validator


class NotificationTypeEnum(str, Enum):
    """알림 타입"""
    delay = "delay"
    gate_change = "gate_change"
    cancel = "cancel"
    terminal_change = "terminal_change"


def _as_utc(dt: datetime | None) -> datetime | None:
    """DB에는 tzinfo 없는 UTC 시각으로 저장되므로, 응답 직렬화 시
    tzinfo를 명시해 클라이언트가 로컬 시간으로 오인하지 않게 한다."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class NotificationResponse(BaseModel):
    """알림 상세 응답"""
    notification_id: int
    flight_pk: int
    notification_type: NotificationTypeEnum
    message: str | None
    sent_to: str | None
    sent_at: datetime | None
    is_sent: bool
    error_message: str | None

    model_config = ConfigDict(from_attributes=True)

    _normalize_sent_at = field_validator("sent_at")(_as_utc)


class NotificationListResponse(BaseModel):
    """알림 목록 응답 (간소화된 정보)"""
    notification_id: int
    flight_pk: int
    notification_type: NotificationTypeEnum
    message: str | None
    sent_at: datetime | None
    is_sent: bool

    model_config = ConfigDict(from_attributes=True)

    _normalize_sent_at = field_validator("sent_at")(_as_utc)