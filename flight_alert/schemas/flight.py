# flight_alert/schemas/flight.py
"""
Flight Schemas
비행편 관련 요청/응답 스키마
"""

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class FlightType(str, Enum):
    """비행편 타입"""
    departure = "departure"
    arrival = "arrival"


class FlightCreate(BaseModel):
    """비행편 등록 요청"""
    flight_id: str = Field(..., min_length=2, max_length=10, description="항공편명 (예: KE123)")
    flight_date: date = Field(..., description="출발/도착 날짜 (YYYY-MM-DD)")
    flight_type: FlightType = Field(..., description="'departure' or 'arrival'")


class FlightResponse(BaseModel):
    """비행편 상세 응답"""
    flight_pk: int
    user_id: int 
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
    # 인천공항 OpenAPI에서 운항 정보를 보강했는지 여부.
    # False면 항공사·게이트·시간 등 부가 필드가 비어 있을 수 있음.
    enriched: bool = True
    # API 동기화 상태: ok | failed | pending | manual
    api_sync_status: str | None = None
    # 읽기 전용 공유 링크 토큰 (공유 중이면 값 있음)
    share_token: str | None = None

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