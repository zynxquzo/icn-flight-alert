# flight_alert/repositories/notification_repository.py

from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from flight_alert.models.notification import Notification
from flight_alert.models.flight import Flight


class NotificationRepository:
    def find_by_flight_pk(self, db: Session, flight_pk: int) -> list[Notification]:
        """특정 비행편의 알림 목록 조회"""
        stmt = select(Notification).where(
            Notification.flight_pk == flight_pk
        ).order_by(Notification.sent_at.desc())
        
        result = db.scalars(stmt)
        return result.all()

    def find_by_user_email(
        self, 
        db: Session, 
        user_email: str,
        notification_type: str | None = None
    ) -> list[Notification]:
        """사용자 이메일로 알림 목록 조회
        
        사용자가 등록한 모든 비행편의 알림을 조회
        """
        stmt = (
            select(Notification)
            .join(Flight, Notification.flight_pk == Flight.flight_pk)
            .where(Flight.user_email == user_email)
        )
        
        if notification_type:
            stmt = stmt.where(Notification.notification_type == notification_type)
        
        stmt = stmt.order_by(Notification.sent_at.desc())
        
        result = db.scalars(stmt)
        return result.all()

    def find_by_id(self, db: Session, notification_id: int) -> Notification | None:
        """PK로 알림 조회"""
        stmt = select(Notification).where(Notification.notification_id == notification_id)
        return db.scalar(stmt)

    def save(self, db: Session, notification: Notification) -> Notification:
        """알림 저장"""
        db.add(notification)
        db.flush()
        db.refresh(notification)
        return notification

    def update(self, db: Session, notification: Notification) -> Notification:
        """알림 업데이트"""
        db.flush()
        db.refresh(notification)
        return notification


notification_repository = NotificationRepository()