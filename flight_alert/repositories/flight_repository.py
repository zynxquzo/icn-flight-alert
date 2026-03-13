# flight_alert/repositories/flight_repository.py

from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select
from flight_alert.models.flight import Flight


class FlightRepository:
    def find_all_by_email(
        self, 
        db: Session, 
        user_email: str, 
        is_active: bool | None = None
    ) -> list[Flight]:
        """이메일로 비행편 목록 조회"""
        stmt = select(Flight).where(Flight.user_email == user_email)
        
        if is_active is not None:
            stmt = stmt.where(Flight.is_active == is_active)
        
        result = db.scalars(stmt)
        return result.all()

    def find_by_id(self, db: Session, flight_pk: int) -> Flight | None:
        """PK로 비행편 조회"""
        stmt = select(Flight).where(Flight.flight_pk == flight_pk)
        return db.scalar(stmt)

    def save(self, db: Session, flight: Flight) -> Flight:
        """비행편 저장"""
        db.add(flight)
        db.flush()  # ID 즉시 생성
        db.refresh(flight)
        return flight

    def delete(self, db: Session, flight: Flight) -> None:
        """비행편 삭제"""
        db.delete(flight)
        db.flush()


flight_repository = FlightRepository()