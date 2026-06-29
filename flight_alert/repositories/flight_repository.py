# flight_alert/repositories/flight_repository.py

from sqlalchemy import select
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


flight_repository = FlightRepository()
