# flight_alert/routers/flight_router.py
# 라우트 순서: 고정 경로는 반드시 동적 경로(/flights/{flight_pk})보다 위에 정의

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from database import get_db
from flight_alert.services.flight_service import flight_service
from flight_alert.schemas.flight import (
    FlightCreate,
    FlightResponse,
    FlightListResponse,
)

router = APIRouter(prefix="/flights", tags=["Flights"])


# --- 고정 경로: 동적 경로보다 항상 위에 정의 ---

@router.post("", response_model=FlightResponse, status_code=status.HTTP_201_CREATED)
def create_flight(
    flight_data: FlightCreate,
    db: Session = Depends(get_db),
):
    """비행편 등록
    
    - 사용자 이메일, 편명, 날짜, 타입(출발/도착)을 입력받아 비행편 등록
    - TODO: 인천공항 OpenAPI 호출하여 실제 비행편 정보 조회
    """
    return flight_service.create_flight(db, flight_data)


@router.get("", response_model=list[FlightListResponse])
def read_flights(
    user_email: str = Query(..., description="사용자 이메일"),
    is_active: bool | None = Query(None, description="활성 상태 필터 (True/False)"),
    db: Session = Depends(get_db),
):
    """비행편 목록 조회
    
    - 사용자 이메일로 등록된 비행편 목록 조회
    - is_active 파라미터로 활성/비활성 필터링 가능
    """
    return flight_service.read_flights(db, user_email, is_active)


# --- 동적 경로: 고정 경로 추가 시 위쪽 고정 경로 섹션에 정의 ---

@router.get("/{flight_pk}", response_model=FlightResponse)
def read_flight(
    flight_pk: int,
    db: Session = Depends(get_db),
):
    """비행편 상세 조회
    
    - flight_pk로 특정 비행편의 상세 정보 조회
    """
    return flight_service.read_flight_detail(db, flight_pk)


@router.delete("/{flight_pk}", status_code=status.HTTP_204_NO_CONTENT)
def delete_flight(
    flight_pk: int,
    db: Session = Depends(get_db),
):
    """비행편 삭제
    
    - flight_pk로 특정 비행편 삭제
    - 삭제 시 관련된 로그와 알림도 함께 삭제됨 (CASCADE)
    """
    flight_service.delete_flight(db, flight_pk)