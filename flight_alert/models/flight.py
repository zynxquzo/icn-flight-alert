# flight_alert/models/flight.py
"""
Flight Model
사용자가 등록한 관심 비행편 정보를 저장하는 테이블
"""

from datetime import datetime, date
from sqlalchemy import String, Date, DateTime, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .flight_status_log import FlightStatusLog
    from .notification import Notification


class Flight(Base):
    """비행편 테이블"""
    __tablename__ = "flights"

    # Primary Key
    flight_pk: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # User Information
    user_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    
    # Flight Basic Information
    flight_id: Mapped[str | None] = mapped_column(String(10), nullable=True)
    flight_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    flight_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    
    # Airline & Airport Information
    airline: Mapped[str | None] = mapped_column(String(50), nullable=True)
    airport: Mapped[str | None] = mapped_column(String(50), nullable=True)
    airport_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    
    # Terminal & Gate Information
    terminal_id: Mapped[str | None] = mapped_column(String(10), nullable=True)
    gate_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    
    # Schedule Information
    schedule_date_time: Mapped[str | None] = mapped_column(String(12), nullable=True)
    estimated_date_time: Mapped[str | None] = mapped_column(String(12), nullable=True)
    
    # Status Information
    remark: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # Departure Only Fields
    chkin_range: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # Arrival Only Fields
    carousel: Mapped[str | None] = mapped_column(String(10), nullable=True)
    exit_number: Mapped[str | None] = mapped_column(String(10), nullable=True)
    
    # System Fields
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    # Relationships
    status_logs: Mapped[list["FlightStatusLog"]] = relationship(
        back_populates="flight", 
        cascade="all, delete-orphan"
    )
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="flight", 
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Flight(flight_pk={self.flight_pk}, flight_id={self.flight_id}, user_email={self.user_email})>"