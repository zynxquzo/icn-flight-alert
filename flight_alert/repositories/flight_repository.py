# flight_alert/repositories/flight_repository.py

from datetime import date

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from flight_alert.models.flight import Flight


class FlightRepository:
    async def find_all_by_email(
        self,
        db: AsyncSession,
        user_email: str,
        is_active: bool | None = None,
    ) -> list[Flight]:
        """이메일로 비행편 목록 조회 (하위 호환)"""
        stmt = select(Flight).where(Flight.user_email == user_email)

        if is_active is not None:
            stmt = stmt.where(Flight.is_active.is_(is_active))

        result = await db.scalars(stmt)
        return list(result.all())

    async def find_all_by_user_id(
        self,
        db: AsyncSession,
        user_id: int,
        is_active: bool | None = None,
    ) -> list[Flight]:
        """user_id로 비행편 목록 조회"""
        stmt = select(Flight).where(Flight.user_id == user_id)

        if is_active is not None:
            stmt = stmt.where(Flight.is_active.is_(is_active))

        result = await db.scalars(stmt)
        return list(result.all())

    async def find_by_id(self, db: AsyncSession, flight_pk: int) -> Flight | None:
        """PK로 비행편 조회"""
        stmt = select(Flight).where(Flight.flight_pk == flight_pk)
        return await db.scalar(stmt)

    async def save(self, db: AsyncSession, flight: Flight) -> Flight:
        """비행편 저장"""
        db.add(flight)
        await db.flush()
        await db.refresh(flight)
        return flight

    async def delete(self, db: AsyncSession, flight: Flight) -> None:
        """비행편 삭제"""
        await db.delete(flight)
        await db.flush()

    async def update(self, db: AsyncSession, flight: Flight) -> Flight:
        """비행편 업데이트"""
        await db.flush()
        await db.refresh(flight)
        return flight

    async def deactivate_expired(self, db: AsyncSession, today: date) -> int:
        """flight_date가 지난 활성 비행편을 비활성화"""
        result = await db.execute(
            update(Flight)
            .where(Flight.is_active.is_(True))
            .where(Flight.flight_date < today)
            .values(is_active=False)
        )
        return result.rowcount

    async def delete_stale_inactive(self, db: AsyncSession, cutoff_date: date) -> int:
        """flight_date가 cutoff_date 이전인 비활성 비행편을 삭제 (보관 기간 만료)"""
        result = await db.execute(
            delete(Flight)
            .where(Flight.is_active.is_(False))
            .where(Flight.flight_date < cutoff_date)
        )
        return result.rowcount


flight_repository = FlightRepository()
