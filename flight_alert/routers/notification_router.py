# flight_alert/routers/notification_router.py

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

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
def read_flight_notifications(
    flight_pk: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """특정 비행편의 알림 목록 조회 (로그인 필수, 본인 비행편만)

    - flight_pk로 해당 비행편의 모든 알림 조회
    - 최근 발송 순으로 정렬
    """
    flight = flight_service.read_flight_by_id(db, flight_pk)
    if flight.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="본인의 비행편 알림만 조회할 수 있습니다.",
        )
    return notification_service.read_flight_notifications(db, flight_pk)


@router.get("", response_model=list[NotificationResponse])
def read_user_notifications(
    current_user: User = Depends(get_current_user),
    notification_type: str | None = Query(
        None,
        description="알림 타입 필터 (delay/gate_change/cancel/terminal_change)",
    ),
    db: Session = Depends(get_db),
):
    """로그인한 사용자의 모든 알림 조회

    - 등록한 모든 비행편의 알림 조회
    - notification_type으로 특정 타입만 필터링 가능
    - 최근 발송 순으로 정렬
    """
    return notification_service.read_user_notifications(
        db, current_user.email, notification_type
    )
