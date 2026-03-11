# flight_alert/models/flight_status_log.py
"""
FlightStatusLog Model
비행편 상태 변경 이력을 추적하는 테이블
"""

from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .flight import Flight


class FlightStatusLog(Base):
    """비행편 상태 변경 로그 테이블"""
    __tablename__ = "flight_status_logs"

    # Primary Key
    log_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Foreign Key
    flight_pk: Mapped[int] = mapped_column(
        ForeignKey("flights.flight_pk", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    
    # Schedule Information (변경 시점의 값 저장)
    schedule_date_time: Mapped[str | None] = mapped_column(String(12), nullable=True)
    estimated_date_time: Mapped[str | None] = mapped_column(String(12), nullable=True)
    
    # Terminal & Gate Information
    terminal_id: Mapped[str | None] = mapped_column(String(10), nullable=True)
    gate_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    
    # Status Information
    remark: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # Arrival Only
    carousel: Mapped[str | None] = mapped_column(String(10), nullable=True)
    
    # Change Information
    change_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    
    # System Fields
    detected_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationship
    flight: Mapped["Flight"] = relationship(back_populates="status_logs")

    def __repr__(self):
        return f"<FlightStatusLog(log_id={self.log_id}, flight_pk={self.flight_pk}, change_type={self.change_type})>"