# flight_alert/services/notification_service.py

import logging
from sqlalchemy.orm import Session

from flight_alert.exceptions import NotFoundException
from flight_alert.models.notification import Notification
from flight_alert.repositories.notification_repository import notification_repository
from flight_alert.repositories.flight_repository import flight_repository
from flight_alert.schemas.notification import (
    NotificationResponse,
    NotificationListResponse,
)

logger = logging.getLogger(__name__)


class NotificationService:
    def read_flight_notifications(
        self, 
        db: Session, 
        flight_pk: int
    ) -> list[NotificationListResponse]:
        """특정 비행편의 알림 목록 조회"""
        # 비행편 존재 확인
        flight = flight_repository.find_by_id(db, flight_pk)
        if not flight:
            raise NotFoundException(f"존재하지 않는 비행편입니다. (flight_pk={flight_pk})")
        
        notifications = notification_repository.find_by_flight_pk(db, flight_pk)
        
        return [
            NotificationListResponse(
                notification_id=notif.notification_id,
                flight_pk=notif.flight_pk,
                notification_type=notif.notification_type.value,
                message=notif.message,
                sent_at=notif.sent_at,
                is_sent=notif.is_sent,
            )
            for notif in notifications
        ]

    def read_user_notifications(
        self, 
        db: Session, 
        user_email: str,
        notification_type: str | None = None
    ) -> list[NotificationResponse]:
        """사용자의 모든 알림 조회"""
        notifications = notification_repository.find_by_user_email(
            db, 
            user_email, 
            notification_type
        )
        
        return [
            NotificationResponse(
                notification_id=notif.notification_id,
                flight_pk=notif.flight_pk,
                notification_type=notif.notification_type.value,
                message=notif.message,
                sent_to=notif.sent_to,
                sent_at=notif.sent_at,
                is_sent=notif.is_sent,
                error_message=notif.error_message,
            )
            for notif in notifications
        ]


notification_service = NotificationService()