# flight_alert/routers/flight_router.py
# 라우트 순서: 고정 경로는 반드시 동적 경로(/flights/{flight_pk})보다 위에 정의

from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

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


@router.post("", response_model=FlightResponse, status_code=status.HTTP_201_CREATED)
async def create_flight(
    flight_data: FlightCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """비행편 등록 (로그인 필수)"""
    return await flight_service.create_flight(
        db,
        flight_data,
        user_id=current_user.user_id,
        user_email=current_user.email,
    )


@router.get("", response_model=list[FlightListResponse])
async def read_flights(
    is_active: bool | None = Query(None, description="활성 상태 필터 (True/False)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """내 비행편 목록 조회 (로그인 필수)"""
    return await flight_service.read_flights(db, current_user.user_id, is_active)


@router.get("/{flight_pk}", response_model=FlightResponse)
async def read_flight(
    flight_pk: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """비행편 상세 조회 (로그인 필수, 본인만)"""
    flight = await flight_service.read_flight_by_id(db, flight_pk)

    if flight.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="본인의 비행편만 조회할 수 있습니다.",
        )

    return await flight_service.read_flight_detail(db, flight_pk)


@router.delete("/{flight_pk}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flight(
    flight_pk: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """비행편 삭제 (로그인 필수, 본인만)"""
    flight = await flight_service.read_flight_by_id(db, flight_pk)

    if flight.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="본인의 비행편만 삭제할 수 있습니다.",
        )

    await flight_service.delete_flight(db, flight_pk)


@router.patch("/{flight_pk}/status", response_model=FlightResponse)
async def update_flight_status(
    flight_pk: int,
    status_data: FlightUpdateStatus,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """비행편 활성화 상태 변경 (로그인 필수, 본인만)"""
    flight = await flight_service.read_flight_by_id(db, flight_pk)

    if flight.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="본인의 비행편만 수정할 수 있습니다.",
        )

    return await flight_service.update_flight_status(db, flight_pk, status_data.is_active)


@router.post("/{flight_pk}/refresh")
async def refresh_flight(
    flight_pk: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """비행편 정보 수동 갱신 (로그인 필수, 본인만)"""
    flight = await flight_service.read_flight_by_id(db, flight_pk)

    if flight.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="본인의 비행편만 갱신할 수 있습니다.",
        )

    return await flight_service.refresh_flight(db, flight_pk)


@router.get("/{flight_pk}/logs", response_model=list[FlightStatusLogResponse])
async def read_flight_logs(
    flight_pk: int,
    change_type: str | None = Query(
        None,
        description="변경 타입 필터 (gate_change/delay/status_change/terminal_change)",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """비행편 상태 변경 이력 조회 (로그인 필수, 본인만)"""
    flight = await flight_service.read_flight_by_id(db, flight_pk)
    if flight.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="본인의 비행편 로그만 조회할 수 있습니다.",
        )
    return await flight_status_log_service.read_flight_logs(db, flight_pk, change_type)
