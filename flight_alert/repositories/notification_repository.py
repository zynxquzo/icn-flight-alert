# flight_alert/repositories/notification_repository.py

from sqlalchemy import false, select
from sqlalchemy.ext.asyncio import AsyncSession

from flight_alert.models.flight import Flight
from flight_alert.models.notification import Notification, NotificationType


class NotificationRepository:
    async def find_by_flight_pk(
        self, db: AsyncSession, flight_pk: int
    ) -> list[Notification]:
        """특정 비행편의 알림 목록 조회"""
        stmt = (
            select(Notification)
            .where(Notification.flight_pk == flight_pk)
            .order_by(Notification.sent_at.desc())
        )

        result = await db.scalars(stmt)
        return list(result.all())

    async def find_by_user_email(
        self,
        db: AsyncSession,
        user_email: str,
        notification_type: str | None = None,
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
            try:
                nt_enum = NotificationType(notification_type)
            except ValueError:
                stmt = stmt.where(false())
            else:
                stmt = stmt.where(Notification.notification_type == nt_enum)

        stmt = stmt.order_by(Notification.sent_at.desc())

        result = await db.scalars(stmt)
        return list(result.all())

    async def find_by_id(
        self, db: AsyncSession, notification_id: int
    ) -> Notification | None:
        """PK로 알림 조회"""
        stmt = select(Notification).where(
            Notification.notification_id == notification_id
        )
        return await db.scalar(stmt)

    async def save(self, db: AsyncSession, notification: Notification) -> Notification:
        """알림 저장"""
        db.add(notification)
        await db.flush()
        await db.refresh(notification)
        return notification

    async def update(
        self, db: AsyncSession, notification: Notification
    ) -> Notification:
        """알림 업데이트"""
        await db.flush()
        await db.refresh(notification)
        return notification


notification_repository = NotificationRepository()
