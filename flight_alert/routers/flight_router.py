# flight_alert/routers/flight_router.py
# 라우트 순서: 고정 경로는 반드시 동적 경로(/flights/{flight_pk})보다 위에 정의

from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from flight_alert.dependencies import get_current_user
from flight_alert.models.user import User
from flight_alert.services.flight_service import flight_service
from flight_alert.services.flight_status_log_service import flight_status_log_service
from flight_alert.schemas.flight import (
    FlightCreate,
    FlightResponse,
    FlightListResponse,
    FlightUpdateStatus,
)
from flight_alert.schemas.flight_status_log import FlightStatusLogResponse

router = APIRouter(prefix="/flights", tags=["Flights"])


# --- 고정 경로: 동적 경로보다 항상 위에 정의 ---

@router.post("", response_model=FlightResponse, status_code=status.HTTP_201_CREATED)
def create_flight(
    flight_data: FlightCreate,
    current_user: User = Depends(get_current_user),  # ✅ 인증 추가
    db: Session = Depends(get_db),
):
    """비행편 등록 (로그인 필수)
    
    - 편명, 날짜, 타입(출발/도착)을 입력받아 비행편 등록
    - 로그인한 사용자의 이메일로 자동 등록
    """
    return flight_service.create_flight(
        db, 
        flight_data, 
        user_id=current_user.user_id,
        user_email=current_user.email
    )


@router.get("", response_model=list[FlightListResponse])
def read_flights(
    is_active: bool | None = Query(None, description="활성 상태 필터 (True/False)"),
    current_user: User = Depends(get_current_user),  # ✅ 인증 추가
    db: Session = Depends(get_db),
):
    """내 비행편 목록 조회 (로그인 필수)
    
    - 로그인한 사용자의 비행편만 조회
    - is_active 파라미터로 활성/비활성 필터링 가능
    """
    return flight_service.read_flights(db, current_user.user_id, is_active)


# --- 동적 경로: 고정 경로 추가 시 위쪽 고정 경로 섹션에 정의 ---

@router.get("/{flight_pk}", response_model=FlightResponse)
def read_flight(
    flight_pk: int,
    current_user: User = Depends(get_current_user),  # ✅ 인증 추가
    db: Session = Depends(get_db),
):
    """비행편 상세 조회 (로그인 필수, 본인만)
    
    - flight_pk로 특정 비행편의 상세 정보 조회
    - 본인 비행편만 조회 가능
    """
    flight = flight_service.read_flight_by_id(db, flight_pk)
    
    # 본인 확인
    if flight.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="본인의 비행편만 조회할 수 있습니다."
        )
    
    return flight_service.read_flight_detail(db, flight_pk)


@router.delete("/{flight_pk}", status_code=status.HTTP_204_NO_CONTENT)
def delete_flight(
    flight_pk: int,
    current_user: User = Depends(get_current_user),  # ✅ 인증 추가
    db: Session = Depends(get_db),
):
    """비행편 삭제 (로그인 필수, 본인만)
    
    - flight_pk로 특정 비행편 삭제
    - 본인 비행편만 삭제 가능
    - 삭제 시 관련된 로그와 알림도 함께 삭제됨 (CASCADE)
    """
    flight = flight_service.read_flight_by_id(db, flight_pk)
    
    # 본인 확인
    if flight.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="본인의 비행편만 삭제할 수 있습니다."
        )
    
    flight_service.delete_flight(db, flight_pk)


@router.patch("/{flight_pk}/status", response_model=FlightResponse)
def update_flight_status(
    flight_pk: int,
    status_data: FlightUpdateStatus,
    current_user: User = Depends(get_current_user),  # ✅ 인증 추가
    db: Session = Depends(get_db),
):
    """비행편 활성화 상태 변경 (로그인 필수, 본인만)
    
    - is_active를 true/false로 변경하여 모니터링 활성화/비활성화
    - 본인 비행편만 변경 가능
    - 비활성화된 비행편은 스케줄러에서 조회하지 않음
    """
    flight = flight_service.read_flight_by_id(db, flight_pk)
    
    # 본인 확인
    if flight.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="본인의 비행편만 수정할 수 있습니다."
        )
    
    return flight_service.update_flight_status(db, flight_pk, status_data.is_active)


@router.post("/{flight_pk}/refresh")
def refresh_flight(
    flight_pk: int,
    current_user: User = Depends(get_current_user),  # ✅ 인증 추가
    db: Session = Depends(get_db),
):
    """비행편 정보 수동 갱신 (로그인 필수, 본인만)
    
    - 인천공항 OpenAPI를 호출하여 최신 비행편 정보로 업데이트
    - 본인 비행편만 갱신 가능
    - 변경 사항(게이트, 터미널, 지연 등) 감지 및 반환
    """
    flight = flight_service.read_flight_by_id(db, flight_pk)
    
    # 본인 확인
    if flight.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="본인의 비행편만 갱신할 수 있습니다."
        )
    
    return flight_service.refresh_flight(db, flight_pk)


@router.get("/{flight_pk}/logs", response_model=list[FlightStatusLogResponse])
def read_flight_logs(
    flight_pk: int,
    change_type: str | None = Query(None, description="변경 타입 필터 (gate_change/delay/status_change/terminal_change)"),
    db: Session = Depends(get_db),
):
    """비행편 상태 변경 이력 조회
    
    - flight_pk로 해당 비행편의 모든 상태 변경 로그 조회
    - change_type으로 특정 변경 타입만 필터링 가능
    - 최근 감지 순으로 정렬
    """
    return flight_status_log_service.read_flight_logs(db, flight_pk, change_type)