# flight_alert/services/flight_service.py

import logging
from datetime import datetime, date
from sqlalchemy.orm import Session

from flight_alert.models.flight import Flight
from flight_alert.repositories.flight_repository import flight_repository
from flight_alert.services.incheon_api_service import incheon_api_service
from flight_alert.services.email_service import email_service
from flight_alert.exceptions import NotFoundException
from flight_alert.schemas.flight import (
    FlightCreate,
    FlightResponse,
    FlightListResponse,
)

logger = logging.getLogger(__name__)


class FlightService:
    def create_flight(
        self, 
        db: Session, 
        flight_data: FlightCreate,
        user_id: int,
        user_email: str
    ) -> Flight:
        """비행편 등록
        
        인천공항 API 호출하여 실제 비행편 정보 조회 후 저장
        """
        # 인천공항 API 호출
        api_data = incheon_api_service.get_flight_info(
            flight_id=flight_data.flight_id,
            flight_date=flight_data.flight_date,
            flight_type=flight_data.flight_type.value,
            airport_code=None  # 전체 검색
        )
        
        # API 호출 실패 시 기본 정보만 저장
        if not api_data:
            logger.warning(f"API 호출 실패 - 기본 정보만 저장: {flight_data.flight_id}")
            flight = Flight(
                user_id=user_id,  # ✅ 추가
                user_email=user_email,  # ✅ 수정
                flight_id=flight_data.flight_id,
                flight_date=flight_data.flight_date,
                flight_type=flight_data.flight_type.value,
                is_active=True,
            )
        else:
            # API 데이터로 Flight 객체 생성
            flight = Flight(
                user_id=user_id,  # ✅ 추가
                user_email=user_email,  # ✅ 수정
                flight_id=api_data.get('flightId'),
                flight_date=flight_data.flight_date,
                flight_type=flight_data.flight_type.value,
                airline=api_data.get('airline'),
                airport=api_data.get('airport'),
                airport_code=api_data.get('airportCode'),
                terminal_id=api_data.get('terminalid'),
                gate_number=api_data.get('gatenumber'),
                schedule_date_time=api_data.get('scheduleDateTime'),
                estimated_date_time=api_data.get('estimatedDateTime'),
                remark=api_data.get('remark'),
                chkin_range=api_data.get('chkinrange'),  # 출발편만
                carousel=api_data.get('carousel'),  # 도착편만
                exit_number=api_data.get('exitnumber'),  # 도착편만
                is_active=True,
            )
        
        saved_flight = flight_repository.save(db, flight)
        db.commit()
        
        logger.info(f"비행편 등록 완료: flight_pk={saved_flight.flight_pk}, flight_id={saved_flight.flight_id}")
        return saved_flight

    def read_flights(
        self, 
        db: Session, 
        user_id: int, 
        is_active: bool | None = None
    ) -> list[FlightListResponse]:
        """비행편 목록 조회 (로그인한 사용자의 비행편만)"""
        flights = flight_repository.find_all_by_user_id(db, user_id, is_active)
        
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
            raise NotFoundException(f"존재하지 않는 비행편입니다. (flight_pk={flight_pk})")
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
        변경사항이 있으면 로그 생성 및 알림 생성
        
        Returns:
            dict: 변경 사항 정보
        """
        from datetime import datetime, timezone
        from flight_alert.models.flight_status_log import FlightStatusLog
        from flight_alert.models.notification import Notification, NotificationType
        
        flight = self.read_flight_by_id(db, flight_pk)
        
        # 기존 값 저장 (변경 감지용)
        old_gate = flight.gate_number
        old_terminal = flight.terminal_id
        old_estimated = flight.estimated_date_time
        old_remark = flight.remark
        
        # 인천공항 API 호출
        api_data = incheon_api_service.get_flight_info(
            flight_id=flight.flight_id,
            flight_date=flight.flight_date,
            flight_type=flight.flight_type,
            airport_code=flight.airport_code
        )
        
        # API 응답 데이터로 업데이트
        if api_data:
            flight.airline = api_data.get('airline')
            flight.airport = api_data.get('airport')
            flight.airport_code = api_data.get('airportCode')
            flight.terminal_id = api_data.get('terminalid')
            flight.gate_number = api_data.get('gatenumber')
            flight.schedule_date_time = api_data.get('scheduleDateTime')
            flight.estimated_date_time = api_data.get('estimatedDateTime')
            flight.remark = api_data.get('remark')
            flight.chkin_range = api_data.get('chkinrange')  # 출발편만
            flight.carousel = api_data.get('carousel')  # 도착편만
            flight.exit_number = api_data.get('exitnumber')  # 도착편만
        else:
            logger.warning(f"API 호출 실패 - 기존 데이터 유지: flight_pk={flight_pk}")
        
        # 마지막 조회 시각 업데이트
        flight.last_checked_at = datetime.now(timezone.utc)
        
        # 변경 사항 감지 및 로그/알림 생성
        changes = []
        
        # 게이트 변경 감지
        if old_gate != flight.gate_number:
            change_info = {
                "field": "gate_number",
                "old_value": old_gate,
                "new_value": flight.gate_number,
                "change_type": "gate_change"
            }
            changes.append(change_info)
            
            # FlightStatusLog 생성
            log = FlightStatusLog(
                flight_pk=flight_pk,
                schedule_date_time=flight.schedule_date_time,
                estimated_date_time=flight.estimated_date_time,
                terminal_id=flight.terminal_id,
                gate_number=flight.gate_number,
                remark=flight.remark,
                carousel=flight.carousel,
                change_type="gate_change",
            )
            db.add(log)
            
            # Notification 생성
            message = f"게이트가 {old_gate}에서 {flight.gate_number}로 변경되었습니다"
            notification = Notification(
                flight_pk=flight_pk,
                notification_type=NotificationType.gate_change,
                message=message,
                sent_to=flight.user_email,
                sent_at=datetime.now(timezone.utc),
                is_sent=False,
            )
            db.add(notification)
            db.flush()  # notification_id 생성
            
            # 이메일 발송
            email_sent = email_service.send_notification_email(
                to_email=flight.user_email,
                subject=f"[게이트 변경] {flight.flight_id} - 인천공항 알림",
                message=message,
                flight_id=flight.flight_id,
            )
            
            if email_sent:
                notification.is_sent = True
                logger.info(f"✅ 이메일 발송 성공: {flight.user_email}")
            else:
                logger.error(f"❌ 이메일 발송 실패: {flight.user_email}")
            
            logger.info(f"게이트 변경 감지: {old_gate} → {flight.gate_number}")
        
        # 터미널 변경 감지
        if old_terminal != flight.terminal_id:
            change_info = {
                "field": "terminal_id",
                "old_value": old_terminal,
                "new_value": flight.terminal_id,
                "change_type": "terminal_change"
            }
            changes.append(change_info)
            
            # FlightStatusLog 생성
            log = FlightStatusLog(
                flight_pk=flight_pk,
                schedule_date_time=flight.schedule_date_time,
                estimated_date_time=flight.estimated_date_time,
                terminal_id=flight.terminal_id,
                gate_number=flight.gate_number,
                remark=flight.remark,
                carousel=flight.carousel,
                change_type="terminal_change",
            )
            db.add(log)
            
            # Notification 생성
            message = f"터미널이 {old_terminal}에서 {flight.terminal_id}로 변경되었습니다"
            notification = Notification(
                flight_pk=flight_pk,
                notification_type=NotificationType.terminal_change,
                message=message,
                sent_to=flight.user_email,
                sent_at=datetime.now(timezone.utc),
                is_sent=False,
            )
            db.add(notification)
            db.flush()
            
            # 이메일 발송
            email_sent = email_service.send_notification_email(
                to_email=flight.user_email,
                subject=f"[터미널 변경] {flight.flight_id} - 인천공항 알림",
                message=message,
                flight_id=flight.flight_id,
            )
            
            if email_sent:
                notification.is_sent = True
                logger.info(f"✅ 이메일 발송 성공: {flight.user_email}")
            else:
                logger.error(f"❌ 이메일 발송 실패: {flight.user_email}")
            
            logger.info(f"터미널 변경 감지: {old_terminal} → {flight.terminal_id}")
        
        # 지연 감지
        if old_estimated != flight.estimated_date_time:
            change_info = {
                "field": "estimated_date_time",
                "old_value": old_estimated,
                "new_value": flight.estimated_date_time,
                "change_type": "delay"
            }
            changes.append(change_info)
            
            # FlightStatusLog 생성
            log = FlightStatusLog(
                flight_pk=flight_pk,
                schedule_date_time=flight.schedule_date_time,
                estimated_date_time=flight.estimated_date_time,
                terminal_id=flight.terminal_id,
                gate_number=flight.gate_number,
                remark=flight.remark,
                carousel=flight.carousel,
                change_type="delay",
            )
            db.add(log)
            
            # 지연 시간 계산
            if old_estimated and flight.estimated_date_time:
                message = f"출발/도착 시각이 변경되었습니다 ({old_estimated} → {flight.estimated_date_time})"
            else:
                message = f"출발/도착 시각이 업데이트되었습니다"
            
            # Notification 생성
            notification = Notification(
                flight_pk=flight_pk,
                notification_type=NotificationType.delay,
                message=message,
                sent_to=flight.user_email,
                sent_at=datetime.now(timezone.utc),
                is_sent=False,
            )
            db.add(notification)
            db.flush()
            
            # 이메일 발송
            email_sent = email_service.send_notification_email(
                to_email=flight.user_email,
                subject=f"[시간 변경] {flight.flight_id} - 인천공항 알림",
                message=message,
                flight_id=flight.flight_id,
            )
            
            if email_sent:
                notification.is_sent = True
                logger.info(f"✅ 이메일 발송 성공: {flight.user_email}")
            else:
                logger.error(f"❌ 이메일 발송 실패: {flight.user_email}")
            
            logger.info(f"지연 감지: {old_estimated} → {flight.estimated_date_time}")
        
        # 운항 상태 변경 감지
        if old_remark != flight.remark:
            change_info = {
                "field": "remark",
                "old_value": old_remark,
                "new_value": flight.remark,
                "change_type": "status_change"
            }
            changes.append(change_info)
            
            # FlightStatusLog 생성
            log = FlightStatusLog(
                flight_pk=flight_pk,
                schedule_date_time=flight.schedule_date_time,
                estimated_date_time=flight.estimated_date_time,
                terminal_id=flight.terminal_id,
                gate_number=flight.gate_number,
                remark=flight.remark,
                carousel=flight.carousel,
                change_type="status_change",
            )
            db.add(log)
            
            # 결항 여부 확인
            if flight.remark and "결항" in flight.remark:
                notification_type = NotificationType.cancel
                message = f"비행편이 결항되었습니다"
            else:
                # 일반 상태 변경은 알림 생성하지 않음 (너무 많아질 수 있음)
                notification_type = None
                message = None
            
            if notification_type:
                # Notification 생성
                notification = Notification(
                    flight_pk=flight_pk,
                    notification_type=notification_type,
                    message=message,
                    sent_to=flight.user_email,
                    sent_at=datetime.now(timezone.utc),
                    is_sent=False,
                )
                db.add(notification)
                db.flush()
                
                # 이메일 발송
                email_sent = email_service.send_notification_email(
                    to_email=flight.user_email,
                    subject=f"[결항] {flight.flight_id} - 인천공항 알림",
                    message=message,
                    flight_id=flight.flight_id,
                )
                
                if email_sent:
                    notification.is_sent = True
                    logger.info(f"✅ 이메일 발송 성공: {flight.user_email}")
                else:
                    logger.error(f"❌ 이메일 발송 실패: {flight.user_email}")
                
                logger.info(f"운항 상태 변경 감지: {old_remark} → {flight.remark}")
        
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