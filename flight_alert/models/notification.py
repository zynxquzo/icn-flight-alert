# flight_alert/models/notification.py
"""
Notification Model
비행편 변경 알림 이력을 저장하는 테이블
"""

from datetime import datetime
from sqlalchemy import String, DateTime, Boolean, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base
from typing import TYPE_CHECKING
import enum

if TYPE_CHECKING:
    from .flight import Flight


class NotificationType(enum.Enum):
    """알림 타입 ENUM"""
    delay = "delay"
    gate_change = "gate_change"
    cancel = "cancel"
    terminal_change = "terminal_change"


class Notification(Base):
    """알림 테이블"""
    __tablename__ = "notifications"

    # Primary Key
    notification_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Foreign Key
    flight_pk: Mapped[int] = mapped_column(
        ForeignKey("flights.flight_pk", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    
    # Notification Information
    notification_type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType), 
        nullable=False
    )
    message: Mapped[str | None] = mapped_column(String, nullable=True)
    
    # Recipient Information
    sent_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Sending Status
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)

    # Relationship
    flight: Mapped["Flight"] = relationship(back_populates="notifications")

    def __repr__(self):
        return f"<Notification(notification_id={self.notification_id}, type={self.notification_type.value}, is_sent={self.is_sent})>"