# flight_alert/schemas/flight.py
"""
Flight Schemas
비행편 관련 요청/응답 스키마
"""

from datetime import datetime, date
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from enum import Enum


class FlightType(str, Enum):
    """비행편 타입"""
    departure = "departure"
    arrival = "arrival"


class FlightCreate(BaseModel):
    """비행편 등록 요청"""
    user_email: EmailStr = Field(..., description="사용자 이메일")
    flight_id: str = Field(..., min_length=2, max_length=10, description="항공편명 (예: KE123)")
    flight_date: date = Field(..., description="출발/도착 날짜 (YYYY-MM-DD)")
    flight_type: FlightType = Field(..., description="'departure' or 'arrival'")


class FlightResponse(BaseModel):
    """비행편 상세 응답"""
    flight_pk: int
    user_email: str
    flight_id: str | None
    flight_date: date | None
    flight_type: str | None
    airline: str | None
    airport: str | None
    airport_code: str | None
    terminal_id: str | None
    gate_number: str | None
    schedule_date_time: str | None
    estimated_date_time: str | None
    remark: str | None
    chkin_range: str | None
    carousel: str | None
    exit_number: str | None
    is_active: bool
    created_at: datetime
    last_checked_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class FlightListResponse(BaseModel):
    """비행편 목록 응답 (간소화된 정보)"""
    flight_pk: int
    flight_id: str | None
    flight_date: date | None
    flight_type: str | None
    airline: str | None
    airport: str | None
    gate_number: str | None
    schedule_date_time: str | None
    estimated_date_time: str | None
    remark: str | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class FlightUpdateStatus(BaseModel):
    """비행편 활성화 상태 변경 요청"""
    is_active: bool = Field(..., description="활성화 여부")