# flight_alert/services/flight_service.py

import logging
from datetime import datetime, date
from sqlalchemy.orm import Session

from flight_alert.models.flight import Flight
from flight_alert.repositories.flight_repository import flight_repository
from flight_alert.schemas.flight import (
    FlightCreate,
    FlightResponse,
    FlightListResponse,
)

logger = logging.getLogger(__name__)


class FlightService:
    def create_flight(self, db: Session, flight_data: FlightCreate) -> Flight:
        """비행편 등록
        
        TODO: 인천공항 API 호출하여 실제 비행편 정보 조회 후 저장
        현재는 기본 정보만 저장
        """
        flight = Flight(
            user_email=flight_data.user_email,
            flight_id=flight_data.flight_id,
            flight_date=flight_data.flight_date,
            flight_type=flight_data.flight_type.value,
            is_active=True,
            last_checked_at=datetime.utcnow(),
        )
        
        # TODO: 인천공항 API 호출
        # api_data = incheon_api_service.get_flight_info(
        #     flight_id=flight_data.flight_id,
        #     flight_date=flight_data.flight_date.strftime("%Y%m%d"),
        #     flight_type=flight_data.flight_type.value
        # )
        # flight.airline = api_data.get('airline')
        # flight.airport = api_data.get('airport')
        # ...
        
        saved_flight = flight_repository.save(db, flight)
        db.commit()
        
        logger.info(f"비행편 등록 완료: flight_pk={saved_flight.flight_pk}, flight_id={saved_flight.flight_id}")
        return saved_flight

    def read_flights(
        self, 
        db: Session, 
        user_email: str, 
        is_active: bool | None = None
    ) -> list[FlightListResponse]:
        """비행편 목록 조회"""
        flights = flight_repository.find_all_by_email(db, user_email, is_active)
        
        return [
            FlightListResponse(
                flight_pk=flight.flight_pk,
                flight_id=flight.flight_id,
                flight_date=flight.flight_date,
                flight_type=flight.flight_type,
                airline=flight.airline,
                airport=flight.airport,
                gate_number=flight.gate_number,
                schedule_date_time=flight.schedule_date_time,
                estimated_date_time=flight.estimated_date_time,
                remark=flight.remark,
                is_active=flight.is_active,
            )
            for flight in flights
        ]

    def read_flight_by_id(self, db: Session, flight_pk: int) -> Flight:
        """비행편 상세 조회"""
        flight = flight_repository.find_by_id(db, flight_pk)
        if not flight:
            raise ValueError(f"존재하지 않는 비행편입니다. (flight_pk={flight_pk})")
        return flight

    def read_flight_detail(self, db: Session, flight_pk: int) -> FlightResponse:
        """비행편 상세 정보 조회"""
        flight = self.read_flight_by_id(db, flight_pk)
        return FlightResponse.model_validate(flight)


flight_service = FlightService()