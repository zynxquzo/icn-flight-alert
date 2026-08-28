# flight_alert/schemas/chat.py
"""챗봇 세션·메시지 Pydantic 스키마."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _as_utc(dt: datetime | None) -> datetime | None:
    """DB에는 tzinfo 없는 UTC 시각으로 저장되므로, 응답 직렬화 시
    tzinfo를 명시해 클라이언트가 로컬 시간으로 오인하지 않게 한다."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class ChatSessionCreate(BaseModel):
    terminal: str = Field(default="T1", description="T1 또는 T2")


class ChatMessageOut(BaseModel):
    message_id: int
    role: str
    content: str
    mode: str | None = None
    sources: list[dict[str, Any]] | None = None
    feedback: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    _normalize_created_at = field_validator("created_at")(_as_utc)


class ChatSessionOut(BaseModel):
    session_id: str
    title: str | None
    terminal: str
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessageOut] = []

    model_config = ConfigDict(from_attributes=True)

    _normalize_created_at = field_validator("created_at")(_as_utc)
    _normalize_updated_at = field_validator("updated_at")(_as_utc)


class ChatSessionSummary(BaseModel):
    session_id: str
    title: str | None
    terminal: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    _normalize_created_at = field_validator("created_at")(_as_utc)
    _normalize_updated_at = field_validator("updated_at")(_as_utc)


class SessionChatRequest(BaseModel):
    message: str
    wait_time_hours: float | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "탑승 게이트가 어디로 바뀌었나요?",
                "wait_time_hours": 2,
            }
        }
    )


class FeedbackRequest(BaseModel):
    feedback: str = Field(
        description="helpful 또는 not_helpful",
        pattern="^(helpful|not_helpful)$",
    )


class FeedbackOut(BaseModel):
    message_id: int
    feedback: str
