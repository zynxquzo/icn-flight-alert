# flight_alert/services/flight_service.py

import logging
import os
from datetime import datetime, date

from sqlalchemy.ext.asyncio import AsyncSession

from flight_alert.exceptions import NotFoundException
from flight_alert.models.flight import Flight
from flight_alert.repositories.flight_repository import flight_repository
from flight_alert.services.email_service import email_service
from flight_alert.services.incheon_api_service import incheon_api_service
from flight_alert.schemas.flight import (
    FlightCreate,
    FlightResponse,
    FlightListResponse,
)

logger = logging.getLogger(__name__)


def _parse_incheon_datetime(value: str | None) -> datetime | None:
    """인천 API 시간 문자열(YYYYMMDDHHmm, 12자)을 datetime으로 파싱."""
    if not value or len(value) < 12:
        return None
    try:
        return datetime.strptime(value[:12], "%Y%m%d%H%M")
    except ValueError:
        return None


def should_notify_delay_for_estimated_change(
    old_estimated: str | None,
    new_estimated: str | None,
    remark: str | None,
) -> bool:
    """estimated_date_time 변경 시 지연/시간변경 알림을 보낼지 여부."""
    if old_estimated == new_estimated:
        return False

    min_diff_minutes = int(os.getenv("FLIGHT_DELAY_MIN_DIFF_MINUTES", "0") or "0")
    dt_old = _parse_incheon_datetime(old_estimated)
    dt_new = _parse_incheon_datetime(new_estimated)
    if min_diff_minutes > 0 and dt_old and dt_new:
        diff_m = abs((dt_new - dt_old).total_seconds()) / 60.0
        if diff_m < min_diff_minutes:
            return False

    hints_raw = (os.getenv("FLIGHT_DELAY_REMARK_HINTS") or "").strip()
    hints = [h.strip() for h in hints_raw.split(",") if h.strip()]
    if hints:
        r = (remark or "").lower()
        if not any(h.lower() in r for h in hints):
            return False

    return True


def _create_status_log_snapshot(flight_pk: int, flight: Flight, change_type: str):
    from flight_alert.models.flight_status_log import FlightStatusLog

    return FlightStatusLog(
        flight_pk=flight_pk,
        schedule_date_time=flight.schedule_date_time,
        estimated_date_time=flight.estimated_date_time,
        terminal_id=flight.terminal_id,
        gate_number=flight.gate_number,
        remark=flight.remark,
        carousel=flight.carousel,
        change_type=change_type,
    )


async def _add_notification_and_email(
    db: AsyncSession,
    flight: Flight,
    flight_pk: int,
    notification_type,
    subject: str,
    message: str,
    *,
    detection_log: str,
) -> None:
    from datetime import timezone

    from flight_alert.models.notification import Notification

    notification = Notification(
        flight_pk=flight_pk,
        notification_type=notification_type,
        message=message,
        sent_to=flight.user_email,
        sent_at=datetime.now(timezone.utc).replace(tzinfo=None),
        is_sent=False,
    )
    db.add(notification)
    await db.flush()

    email_sent = email_service.send_notification_email(
        to_email=flight.user_email,
        subject=subject,
        message=message,
        flight_id=flight.flight_id,
    )

    if email_sent:
        notification.is_sent = True
        logger.info(f"✅ 이메일 발송 성공: {flight.user_email}")
    else:
        logger.error(f"❌ 이메일 발송 실패: {flight.user_email}")

    logger.info(detection_log)


class FlightService:
    async def create_flight(
        self,
        db: AsyncSession,
        flight_data: FlightCreate,
        user_id: int,
        user_email: str,
    ) -> Flight:
        """비행편 등록

        인천공항 API 호출하여 실제 비행편 정보 조회 후 저장
        """
        api_data = await incheon_api_service.get_flight_info(
            flight_id=flight_data.flight_id,
            flight_date=flight_data.flight_date,
            flight_type=flight_data.flight_type.value,
            airport_code=None,
        )
        enriched = bool(api_data)

        if not api_data:
            logger.warning(f"API 호출 실패 - 기본 정보만 저장: {flight_data.flight_id}")
            flight = Flight(
                user_id=user_id,
                user_email=user_email,
                flight_id=flight_data.flight_id,
                flight_date=flight_data.flight_date,
                flight_type=flight_data.flight_type.value,
                is_active=True,
                api_sync_status="failed",
            )
        else:
            flight = Flight(
                user_id=user_id,
                user_email=user_email,
                flight_id=api_data.get("flightId"),
                flight_date=flight_data.flight_date,
                flight_type=flight_data.flight_type.value,
                airline=api_data.get("airline"),
                airport=api_data.get("airport"),
                airport_code=api_data.get("airportCode"),
                terminal_id=api_data.get("terminalid"),
                gate_number=api_data.get("gatenumber"),
                schedule_date_time=api_data.get("scheduleDateTime"),
                estimated_date_time=api_data.get("estimatedDateTime"),
                remark=api_data.get("remark"),
                chkin_range=api_data.get("chkinrange"),
                carousel=api_data.get("carousel"),
                exit_number=api_data.get("exitnumber"),
                is_active=True,
                api_sync_status="ok",
            )

        saved_flight = await flight_repository.save(db, flight)
        await db.commit()

        # FlightResponse(from_attributes=True)가 transient 속성으로 enriched를 읽도록 부착
        saved_flight.enriched = enriched

        logger.info(
            f"비행편 등록 완료: flight_pk={saved_flight.flight_pk}, "
            f"flight_id={saved_flight.flight_id}, enriched={enriched}"
        )
        return saved_flight

    async def read_flights(
        self,
        db: AsyncSession,
        user_id: int,
        is_active: bool | None = None,
    ) -> list[FlightListResponse]:
        """비행편 목록 조회 (로그인한 사용자의 비행편만)"""
        flights = await flight_repository.find_all_by_user_id(db, user_id, is_active)

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

    async def read_flight_by_id(self, db: AsyncSession, flight_pk: int) -> Flight:
        """비행편 상세 조회"""
        flight = await flight_repository.find_by_id(db, flight_pk)
        if not flight:
            raise NotFoundException(f"존재하지 않는 비행편입니다. (flight_pk={flight_pk})")
        return flight

    async def read_flight_detail(self, db: AsyncSession, flight_pk: int) -> FlightResponse:
        """비행편 상세 정보 조회"""
        flight = await self.read_flight_by_id(db, flight_pk)
        return FlightResponse.model_validate(flight)

    async def delete_flight(self, db: AsyncSession, flight_pk: int) -> None:
        """비행편 삭제"""
        flight = await self.read_flight_by_id(db, flight_pk)

        await flight_repository.delete(db, flight)
        await db.commit()

        logger.info(f"비행편 삭제 완료: flight_pk={flight_pk}, flight_id={flight.flight_id}")

    async def update_flight_status(
        self, db: AsyncSession, flight_pk: int, is_active: bool
    ) -> Flight:
        """비행편 활성화 상태 변경"""
        flight = await self.read_flight_by_id(db, flight_pk)

        flight.is_active = is_active

        updated_flight = await flight_repository.update(db, flight)
        await db.commit()

        status_text = "활성화" if is_active else "비활성화"
        logger.info(f"비행편 상태 변경 완료: flight_pk={flight_pk}, {status_text}")

        return updated_flight

    async def refresh_flight(self, db: AsyncSession, flight_pk: int) -> dict:
        """비행편 정보 수동 갱신"""
        from datetime import timezone

        from flight_alert.models.notification import NotificationType

        flight = await self.read_flight_by_id(db, flight_pk)

        old_gate = flight.gate_number
        old_terminal = flight.terminal_id
        old_estimated = flight.estimated_date_time
        old_remark = flight.remark

        api_data = await incheon_api_service.get_flight_info(
            flight_id=flight.flight_id,
            flight_date=flight.flight_date,
            flight_type=flight.flight_type,
            airport_code=flight.airport_code,
        )

        if api_data:
            flight.airline = api_data.get("airline")
            flight.airport = api_data.get("airport")
            flight.airport_code = api_data.get("airportCode")
            flight.terminal_id = api_data.get("terminalid")
            flight.gate_number = api_data.get("gatenumber")
            flight.schedule_date_time = api_data.get("scheduleDateTime")
            flight.estimated_date_time = api_data.get("estimatedDateTime")
            flight.remark = api_data.get("remark")
            flight.chkin_range = api_data.get("chkinrange")
            flight.carousel = api_data.get("carousel")
            flight.exit_number = api_data.get("exitnumber")
            flight.api_sync_status = "ok"
        else:
            flight.api_sync_status = "failed"
            logger.warning(f"API 호출 실패 - 기존 데이터 유지: flight_pk={flight_pk}")

        flight.last_checked_at = datetime.now(timezone.utc).replace(tzinfo=None)

        changes = []

        if old_gate != flight.gate_number:
            changes.append(
                {
                    "field": "gate_number",
                    "old_value": old_gate,
                    "new_value": flight.gate_number,
                    "change_type": "gate_change",
                }
            )
            db.add(_create_status_log_snapshot(flight_pk, flight, "gate_change"))
            await _add_notification_and_email(
                db,
                flight,
                flight_pk,
                NotificationType.gate_change,
                f"[게이트 변경] {flight.flight_id} - 인천공항 알림",
                f"게이트가 {old_gate}에서 {flight.gate_number}로 변경되었습니다",
                detection_log=f"게이트 변경 감지: {old_gate} → {flight.gate_number}",
            )

        if old_terminal != flight.terminal_id:
            changes.append(
                {
                    "field": "terminal_id",
                    "old_value": old_terminal,
                    "new_value": flight.terminal_id,
                    "change_type": "terminal_change",
                }
            )
            db.add(_create_status_log_snapshot(flight_pk, flight, "terminal_change"))
            await _add_notification_and_email(
                db,
                flight,
                flight_pk,
                NotificationType.terminal_change,
                f"[터미널 변경] {flight.flight_id} - 인천공항 알림",
                f"터미널이 {old_terminal}에서 {flight.terminal_id}로 변경되었습니다",
                detection_log=f"터미널 변경 감지: {old_terminal} → {flight.terminal_id}",
            )

        if old_estimated != flight.estimated_date_time:
            notify_delay = should_notify_delay_for_estimated_change(
                old_estimated, flight.estimated_date_time, flight.remark
            )
            est_change_type = "delay" if notify_delay else "eta_adjust"
            changes.append(
                {
                    "field": "estimated_date_time",
                    "old_value": old_estimated,
                    "new_value": flight.estimated_date_time,
                    "change_type": est_change_type,
                }
            )
            db.add(_create_status_log_snapshot(flight_pk, flight, est_change_type))
            if notify_delay:
                if old_estimated and flight.estimated_date_time:
                    msg = (
                        f"출발/도착 시각이 변경되었습니다 "
                        f"({old_estimated} → {flight.estimated_date_time})"
                    )
                else:
                    msg = "출발/도착 시각이 업데이트되었습니다"
                await _add_notification_and_email(
                    db,
                    flight,
                    flight_pk,
                    NotificationType.delay,
                    f"[시간 변경] {flight.flight_id} - 인천공항 알림",
                    msg,
                    detection_log=(
                        f"지연/시간 변경 알림: {old_estimated} → {flight.estimated_date_time}"
                    ),
                )
            else:
                logger.info(
                    "추정시각 변경(알림 생략, FLIGHT_DELAY_* 조건): "
                    f"{old_estimated} → {flight.estimated_date_time}"
                )

        if old_remark != flight.remark:
            changes.append(
                {
                    "field": "remark",
                    "old_value": old_remark,
                    "new_value": flight.remark,
                    "change_type": "status_change",
                }
            )
            db.add(_create_status_log_snapshot(flight_pk, flight, "status_change"))

            if flight.remark and "결항" in flight.remark:
                await _add_notification_and_email(
                    db,
                    flight,
                    flight_pk,
                    NotificationType.cancel,
                    f"[결항] {flight.flight_id} - 인천공항 알림",
                    "비행편이 결항되었습니다",
                    detection_log=f"운항 상태 변경 감지: {old_remark} → {flight.remark}",
                )

        await flight_repository.update(db, flight)
        await db.commit()

        logger.info(
            f"비행편 갱신 완료: flight_pk={flight_pk}, 변경사항={len(changes)}건"
        )

        return {
            "flight_pk": flight_pk,
            "changes_detected": len(changes) > 0,
            "changes": changes,
            "updated_at": flight.last_checked_at,
        }


flight_service = FlightService()
