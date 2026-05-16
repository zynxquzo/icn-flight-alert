# flight_alert/routers/notification_router.py

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from flight_alert.dependencies import get_current_user
from flight_alert.models.user import User
from flight_alert.schemas.notification import (
    NotificationListResponse,
    NotificationResponse,
)
from flight_alert.services.flight_service import flight_service
from flight_alert.services.notification_service import notification_service

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/flights/{flight_pk}", response_model=list[NotificationListResponse])
async def read_flight_notifications(
    flight_pk: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """특정 비행편의 알림 목록 조회 (로그인 필수, 본인 비행편만)"""
    flight = await flight_service.read_flight_by_id(db, flight_pk)
    if flight.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="본인의 비행편 알림만 조회할 수 있습니다.",
        )
    return await notification_service.read_flight_notifications(db, flight_pk)


@router.post("/flights/{flight_pk}/check")
async def check_flight_notifications(
    flight_pk: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """알림 수동 감지: 인천공항 API로 즉시 확인하고, 변경 시 알림·이메일을 생성합니다.

    `POST /flights/{flight_pk}/refresh`와 동일한 처리입니다.
    """
    flight = await flight_service.read_flight_by_id(db, flight_pk)
    if flight.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="본인의 비행편만 알림 감지를 실행할 수 있습니다.",
        )
    return await notification_service.check_flight_notifications(db, flight_pk)


@router.get("", response_model=list[NotificationResponse])
async def read_user_notifications(
    current_user: User = Depends(get_current_user),
    notification_type: str | None = Query(
        None,
        description="알림 타입 필터 (delay/gate_change/cancel/terminal_change)",
    ),
    db: AsyncSession = Depends(get_db),
):
    """로그인한 사용자의 저장된 알림 이력 수동 조회"""
    return await notification_service.read_user_notifications(
        db, current_user.email, notification_type
    )
