# flight_alert/routers/flight_router.py
# 라우트 순서: 고정 경로는 반드시 동적 경로(/flights/{flight_pk})보다 위에 정의

import secrets
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Query, status, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from flight_alert.dependencies import get_current_user
from flight_alert.models.user import User
from flight_alert.services.flight_service import flight_service
from flight_alert.services.flight_status_log_service import flight_status_log_service
from flight_alert.schemas.flight import (
    FlightCreate,
    FlightResponse,
    FlightListResponse,
    FlightUpdateStatus,
)
from flight_alert.schemas.flight_status_log import FlightStatusLogResponse

router = APIRouter(prefix="/flights", tags=["Flights"])


def _generate_ics(flight) -> str:
    """비행편 한 건을 ICS(iCalendar) 텍스트로 변환."""
    def parse_dt(dt_str: str | None) -> datetime | None:
        if not dt_str:
            return None
        try:
            return datetime.strptime(dt_str, "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    start_dt = parse_dt(flight.estimated_date_time or flight.schedule_date_time)
    if start_dt is None and flight.flight_date:
        start_dt = datetime(
            flight.flight_date.year,
            flight.flight_date.month,
            flight.flight_date.day,
            0, 0,
            tzinfo=timezone.utc,
        )
    if start_dt is None:
        start_dt = datetime.now(timezone.utc)
    end_dt = start_dt + timedelta(hours=1)

    fmt = "%Y%m%dT%H%M%SZ"
    flight_type_label = "출발" if (flight.flight_type or "").lower() == "departure" else "도착"
    summary = f"{flight.flight_id or '비행편'} - {flight_type_label} 인천공항"

    loc_parts = []
    if flight.terminal_id:
        loc_parts.append(f"제{flight.terminal_id[-1]}터미널")
    if flight.gate_number:
        loc_parts.append(f"게이트 {flight.gate_number}")
    location = " ".join(loc_parts) if loc_parts else "인천국제공항"

    desc_lines = [
        f"항공편명: {flight.flight_id or '-'}",
        f"날짜: {flight.flight_date or '-'}",
        f"구분: {flight_type_label}",
        f"항공사: {flight.airline or '-'}",
        f"공항: {flight.airport or '인천국제공항'}",
        f"터미널: {flight.terminal_id or '-'}",
        f"게이트: {flight.gate_number or '-'}",
        f"예정 시각: {flight.schedule_date_time or '-'}",
        f"비고: {flight.remark or '-'}",
    ]
    description = "\\n".join(desc_lines)
    uid = f"icn-flight-{flight.flight_pk}@icn-flight-alert"
    now_str = datetime.now(timezone.utc).strftime(fmt)

    return (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//ICN Flight Alert//KO\r\n"
        "CALSCALE:GREGORIAN\r\n"
        "METHOD:PUBLISH\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{uid}\r\n"
        f"DTSTAMP:{now_str}\r\n"
        f"DTSTART:{start_dt.strftime(fmt)}\r\n"
        f"DTEND:{end_dt.strftime(fmt)}\r\n"
        f"SUMMARY:{summary}\r\n"
        f"DESCRIPTION:{description}\r\n"
        f"LOCATION:{location}\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )


@router.post("", response_model=FlightResponse, status_code=status.HTTP_201_CREATED)
async def create_flight(
    flight_data: FlightCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """비행편 등록 (로그인 필수)"""
    return await flight_service.create_flight(
        db,
        flight_data,
        user_id=current_user.user_id,
        user_email=current_user.email,
    )


@router.get("", response_model=list[FlightListResponse])
async def read_flights(
    is_active: bool | None = Query(None, description="활성 상태 필터 (True/False)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """내 비행편 목록 조회 (로그인 필수)"""
    return await flight_service.read_flights(db, current_user.user_id, is_active)


@router.get("/{flight_pk}", response_model=FlightResponse)
async def read_flight(
    flight_pk: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """비행편 상세 조회 (로그인 필수, 본인만)"""
    flight = await flight_service.read_flight_by_id(db, flight_pk)

    if flight.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="본인의 비행편만 조회할 수 있습니다.",
        )

    return await flight_service.read_flight_detail(db, flight_pk)


@router.delete("/{flight_pk}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flight(
    flight_pk: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """비행편 삭제 (로그인 필수, 본인만)"""
    flight = await flight_service.read_flight_by_id(db, flight_pk)

    if flight.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="본인의 비행편만 삭제할 수 있습니다.",
        )

    await flight_service.delete_flight(db, flight_pk)


@router.patch("/{flight_pk}/status", response_model=FlightResponse)
async def update_flight_status(
    flight_pk: int,
    status_data: FlightUpdateStatus,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """비행편 활성화 상태 변경 (로그인 필수, 본인만)"""
    flight = await flight_service.read_flight_by_id(db, flight_pk)

    if flight.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="본인의 비행편만 수정할 수 있습니다.",
        )

    return await flight_service.update_flight_status(db, flight_pk, status_data.is_active)


@router.post("/{flight_pk}/refresh")
async def refresh_flight(
    flight_pk: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """비행편 정보 수동 갱신 (로그인 필수, 본인만)"""
    flight = await flight_service.read_flight_by_id(db, flight_pk)

    if flight.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="본인의 비행편만 갱신할 수 있습니다.",
        )

    return await flight_service.refresh_flight(db, flight_pk)


@router.get("/{flight_pk}/logs", response_model=list[FlightStatusLogResponse])
async def read_flight_logs(
    flight_pk: int,
    change_type: str | None = Query(
        None,
        description="변경 타입 필터 (gate_change/delay/status_change/terminal_change)",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """비행편 상태 변경 이력 조회 (로그인 필수, 본인만)"""
    flight = await flight_service.read_flight_by_id(db, flight_pk)
    if flight.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="본인의 비행편 로그만 조회할 수 있습니다.",
        )
    return await flight_status_log_service.read_flight_logs(db, flight_pk, change_type)


# ---------------------------------------------------------------------------
# ICS 캘린더 내보내기
# ---------------------------------------------------------------------------
@router.get("/{flight_pk}/calendar.ics")
async def download_calendar(
    flight_pk: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """비행편 일정을 iCalendar(.ics) 파일로 내보냅니다."""
    flight = await flight_service.read_flight_by_id(db, flight_pk)
    if flight.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="본인의 비행편만 내보낼 수 있습니다.",
        )
    ics_content = _generate_ics(flight)
    filename = f"flight_{flight.flight_id or flight_pk}.ics"
    return Response(
        content=ics_content,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# 읽기 전용 공유 링크
# ---------------------------------------------------------------------------
@router.post("/{flight_pk}/share", response_model=FlightResponse)
async def create_share_link(
    flight_pk: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """읽기 전용 공유 링크 토큰 생성 (이미 있으면 재사용)."""
    flight = await flight_service.read_flight_by_id(db, flight_pk)
    if flight.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="본인의 비행편만 공유할 수 있습니다.",
        )
    if not flight.share_token:
        flight.share_token = secrets.token_hex(32)
        await db.flush()
        await db.commit()
        await db.refresh(flight)
    return FlightResponse.model_validate(flight)


@router.delete("/{flight_pk}/share", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_share_link(
    flight_pk: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """공유 링크 취소 (share_token 삭제)."""
    flight = await flight_service.read_flight_by_id(db, flight_pk)
    if flight.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="본인의 비행편만 공유 취소할 수 있습니다.",
        )
    flight.share_token = None
    await db.flush()
    await db.commit()


@router.get("/shared/{share_token}", response_model=FlightResponse)
async def read_shared_flight(
    share_token: str,
    db: AsyncSession = Depends(get_db),
):
    """공유 링크로 비행편 읽기 전용 조회 (인증 불필요)."""
    from sqlalchemy import select
    from flight_alert.models.flight import Flight as FlightModel

    flight = await db.scalar(
        select(FlightModel).where(FlightModel.share_token == share_token)
    )
    if not flight:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="유효하지 않은 공유 링크입니다.",
        )
    return FlightResponse.model_validate(flight)
