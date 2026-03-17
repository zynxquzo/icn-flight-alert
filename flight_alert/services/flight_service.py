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

    def delete_flight(self, db: Session, flight_pk: int) -> None:
        """비행편 삭제"""
        flight = self.read_flight_by_id(db, flight_pk)
        
        flight_repository.delete(db, flight)
        db.commit()
        
        logger.info(f"비행편 삭제 완료: flight_pk={flight_pk}, flight_id={flight.flight_id}")

    def update_flight_status(self, db: Session, flight_pk: int, is_active: bool) -> Flight:
        """비행편 활성화 상태 변경"""
        flight = self.read_flight_by_id(db, flight_pk)
        
        # 상태 변경
        flight.is_active = is_active
        
        updated_flight = flight_repository.update(db, flight)
        db.commit()
        
        status_text = "활성화" if is_active else "비활성화"
        logger.info(f"비행편 상태 변경 완료: flight_pk={flight_pk}, {status_text}")
        
        return updated_flight

    def refresh_flight(self, db: Session, flight_pk: int) -> dict:
        """비행편 정보 수동 갱신
        
        인천공항 API를 호출하여 최신 정보로 업데이트하고
        변경사항이 있으면 로그 생성
        
        Returns:
            dict: 변경 사항 정보
        """
        from datetime import datetime, timezone
        
        flight = self.read_flight_by_id(db, flight_pk)
        
        # 기존 값 저장 (변경 감지용)
        old_gate = flight.gate_number
        old_terminal = flight.terminal_id
        old_estimated = flight.estimated_date_time
        old_remark = flight.remark
        
        # TODO: 인천공항 API 호출
        # api_data = incheon_api_service.get_flight_info(
        #     flight_id=flight.flight_id,
        #     flight_date=flight.flight_date.strftime("%Y%m%d"),
        #     flight_type=flight.flight_type
        # )
        # 
        # # API 응답 데이터로 업데이트
        # flight.airline = api_data.get('airline')
        # flight.airport = api_data.get('airport')
        # flight.airport_code = api_data.get('airportCode')
        # flight.terminal_id = api_data.get('terminalid')
        # flight.gate_number = api_data.get('gatenumber')
        # flight.schedule_date_time = api_data.get('scheduleDateTime')
        # flight.estimated_date_time = api_data.get('estimatedDateTime')
        # flight.remark = api_data.get('remark')
        # flight.chkin_range = api_data.get('chkinrange')  # 출발편만
        # flight.carousel = api_data.get('carousel')  # 도착편만
        # flight.exit_number = api_data.get('exitnumber')  # 도착편만
        
        # 마지막 조회 시각 업데이트
        flight.last_checked_at = datetime.now(timezone.utc)
        
        # 변경 사항 감지
        changes = []
        
        if old_gate != flight.gate_number:
            changes.append({
                "field": "gate_number",
                "old_value": old_gate,
                "new_value": flight.gate_number,
                "change_type": "gate_change"
            })
        
        if old_terminal != flight.terminal_id:
            changes.append({
                "field": "terminal_id",
                "old_value": old_terminal,
                "new_value": flight.terminal_id,
                "change_type": "terminal_change"
            })
        
        if old_estimated != flight.estimated_date_time:
            changes.append({
                "field": "estimated_date_time",
                "old_value": old_estimated,
                "new_value": flight.estimated_date_time,
                "change_type": "delay"
            })
        
        if old_remark != flight.remark:
            changes.append({
                "field": "remark",
                "old_value": old_remark,
                "new_value": flight.remark,
                "change_type": "status_change"
            })
        
        # TODO: 변경 사항이 있으면 FlightStatusLog 생성
        # if changes:
        #     for change in changes:
        #         log = FlightStatusLog(
        #             flight_pk=flight_pk,
        #             schedule_date_time=flight.schedule_date_time,
        #             estimated_date_time=flight.estimated_date_time,
        #             terminal_id=flight.terminal_id,
        #             gate_number=flight.gate_number,
        #             remark=flight.remark,
        #             carousel=flight.carousel,
        #             change_type=change['change_type'],
        #         )
        #         db.add(log)
        
        # 업데이트 반영
        flight_repository.update(db, flight)
        db.commit()
        
        logger.info(
            f"비행편 갱신 완료: flight_pk={flight_pk}, "
            f"변경사항={len(changes)}건"
        )
        
        return {
            "flight_pk": flight_pk,
            "changes_detected": len(changes) > 0,
            "changes": changes,
            "updated_at": flight.last_checked_at
        }


flight_service = FlightService()