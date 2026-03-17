# flight_alert/schemas/notification.py
"""
Notification Schemas
알림 관련 응답 스키마
"""

from datetime import datetime
from pydantic import BaseModel, ConfigDict
from enum import Enum


class NotificationTypeEnum(str, Enum):
    """알림 타입"""
    delay = "delay"
    gate_change = "gate_change"
    cancel = "cancel"
    terminal_change = "terminal_change"


class NotificationResponse(BaseModel):
    """알림 상세 응답"""
    notification_id: int
    flight_pk: int
    notification_type: str
    message: str | None
    sent_to: str | None
    sent_at: datetime | None
    is_sent: bool
    error_message: str | None

    model_config = ConfigDict(from_attributes=True)


class NotificationListResponse(BaseModel):
    """알림 목록 응답 (간소화된 정보)"""
    notification_id: int
    flight_pk: int
    notification_type: str
    message: str | None
    sent_at: datetime | None
    is_sent: bool

    model_config = ConfigDict(from_attributes=True)