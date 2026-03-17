# flight_alert/routers/notification_router.py

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from flight_alert.services.notification_service import notification_service
from flight_alert.schemas.notification import (
    NotificationResponse,
    NotificationListResponse,
)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/flights/{flight_pk}", response_model=list[NotificationListResponse])
def read_flight_notifications(
    flight_pk: int,
    db: Session = Depends(get_db),
):
    """특정 비행편의 알림 목록 조회
    
    - flight_pk로 해당 비행편의 모든 알림 조회
    - 최근 발송 순으로 정렬
    """
    return notification_service.read_flight_notifications(db, flight_pk)


@router.get("", response_model=list[NotificationResponse])
def read_user_notifications(
    user_email: str = Query(..., description="사용자 이메일"),
    notification_type: str | None = Query(None, description="알림 타입 필터 (delay/gate_change/cancel/terminal_change)"),
    db: Session = Depends(get_db),
):
    """사용자의 모든 알림 조회
    
    - 사용자가 등록한 모든 비행편의 알림 조회
    - notification_type으로 특정 타입만 필터링 가능
    - 최근 발송 순으로 정렬
    """
    return notification_service.read_user_notifications(db, user_email, notification_type)