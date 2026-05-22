"""비행편 갱신·지연 알림 판단 단위 테스트."""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from flight_alert.models.flight import Flight
from flight_alert.services.flight_service import (
    flight_service,
    should_notify_delay_for_estimated_change,
)
from flight_alert.services.incheon_api_service import incheon_api_service


def _make_flight(**overrides) -> Flight:
    defaults = dict(
        flight_pk=1,
        user_id=1,
        user_email="user@example.com",
        flight_id="KE123",
        flight_date=date(2026, 5, 22),
        flight_type="departure",
        gate_number="114",
        terminal_id="P01",
        schedule_date_time="202605221000",
        estimated_date_time="202605221030",
        remark="출발",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return Flight(**defaults)


class TestShouldNotifyDelay:
    def test_same_estimated_no_notify(self):
        assert (
            should_notify_delay_for_estimated_change(
                "202605221030", "202605221030", "지연"
            )
            is False
        )

    def test_small_diff_suppressed_when_min_diff_set(self, monkeypatch):
        monkeypatch.setenv("FLIGHT_DELAY_MIN_DIFF_MINUTES", "30")
        assert (
            should_notify_delay_for_estimated_change(
                "202605221030", "202605221045", "지연"
            )
            is False
        )

    def test_remark_hint_required(self, monkeypatch):
        monkeypatch.setenv("FLIGHT_DELAY_REMARK_HINTS", "지연,delay")
        assert (
            should_notify_delay_for_estimated_change(
                "202605221030", "202605221100", "출발"
            )
            is False
        )
        assert (
            should_notify_delay_for_estimated_change(
                "202605221030", "202605221100", "지연"
            )
            is True
        )

    def test_notify_on_estimated_change_default(self, monkeypatch):
        monkeypatch.delenv("FLIGHT_DELAY_MIN_DIFF_MINUTES", raising=False)
        monkeypatch.delenv("FLIGHT_DELAY_REMARK_HINTS", raising=False)
        assert (
            should_notify_delay_for_estimated_change(
                "202605221030", "202605221100", None
            )
            is True
        )


@pytest.mark.asyncio
async def test_refresh_flight_detects_gate_change():
    flight = _make_flight()
    mock_db = AsyncMock()
    api_payload = {
        "airline": "대한항공",
        "airport": "나리타",
        "airportCode": "NRT",
        "terminalid": "P01",
        "gatenumber": "115",
        "scheduleDateTime": "202605221000",
        "estimatedDateTime": "202605221030",
        "remark": "출발",
    }

    with (
        patch(
            "flight_alert.services.flight_service.flight_repository.find_by_id",
            new_callable=AsyncMock,
            return_value=flight,
        ),
        patch(
            "flight_alert.services.flight_service.flight_repository.update",
            new_callable=AsyncMock,
            return_value=flight,
        ),
        patch.object(
            incheon_api_service,
            "get_flight_info",
            new_callable=AsyncMock,
            return_value=api_payload,
        ),
        patch(
            "flight_alert.services.flight_service.email_service.send_notification_email",
            return_value=True,
        ),
    ):
        result = await flight_service.refresh_flight(mock_db, 1)

    assert result["changes_detected"] is True
    types = {c["change_type"] for c in result["changes"]}
    assert "gate_change" in types
    assert flight.gate_number == "115"
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_refresh_flight_detects_cancel():
    flight = _make_flight(remark="출발")
    mock_db = AsyncMock()
    api_payload = {
        "airline": "대한항공",
        "terminalid": "P01",
        "gatenumber": "114",
        "scheduleDateTime": "202605221000",
        "estimatedDateTime": "202605221030",
        "remark": "결항",
    }

    with (
        patch(
            "flight_alert.services.flight_service.flight_repository.find_by_id",
            new_callable=AsyncMock,
            return_value=flight,
        ),
        patch(
            "flight_alert.services.flight_service.flight_repository.update",
            new_callable=AsyncMock,
            return_value=flight,
        ),
        patch.object(
            incheon_api_service,
            "get_flight_info",
            new_callable=AsyncMock,
            return_value=api_payload,
        ),
        patch(
            "flight_alert.services.flight_service.email_service.send_notification_email",
            return_value=True,
        ),
    ):
        result = await flight_service.refresh_flight(mock_db, 1)

    assert result["changes_detected"] is True
    assert any(c["change_type"] == "status_change" for c in result["changes"])
    mock_db.add.assert_called()


@pytest.mark.asyncio
async def test_refresh_flight_eta_adjust_without_delay_notification(monkeypatch):
    """작은 시각 변경 + remark 힌트 미충족 시 delay 알림 없이 eta_adjust만 기록."""
    monkeypatch.setenv("FLIGHT_DELAY_MIN_DIFF_MINUTES", "60")
    monkeypatch.setenv("FLIGHT_DELAY_REMARK_HINTS", "지연")

    flight = _make_flight(estimated_date_time="202605221030", remark="출발")
    mock_db = AsyncMock()
    api_payload = {
        "terminalid": "P01",
        "gatenumber": "114",
        "scheduleDateTime": "202605221000",
        "estimatedDateTime": "202605221045",
        "remark": "출발",
    }

    with (
        patch(
            "flight_alert.services.flight_service.flight_repository.find_by_id",
            new_callable=AsyncMock,
            return_value=flight,
        ),
        patch(
            "flight_alert.services.flight_service.flight_repository.update",
            new_callable=AsyncMock,
            return_value=flight,
        ),
        patch.object(
            incheon_api_service,
            "get_flight_info",
            new_callable=AsyncMock,
            return_value=api_payload,
        ),
        patch(
            "flight_alert.services.flight_service.email_service.send_notification_email",
            return_value=True,
        ) as mock_email,
    ):
        result = await flight_service.refresh_flight(mock_db, 1)

    assert result["changes_detected"] is True
    est = next(c for c in result["changes"] if c["field"] == "estimated_date_time")
    assert est["change_type"] == "eta_adjust"
    mock_email.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_flight_no_api_data_keeps_existing():
    flight = _make_flight()
    mock_db = AsyncMock()

    with (
        patch(
            "flight_alert.services.flight_service.flight_repository.find_by_id",
            new_callable=AsyncMock,
            return_value=flight,
        ),
        patch(
            "flight_alert.services.flight_service.flight_repository.update",
            new_callable=AsyncMock,
            return_value=flight,
        ),
        patch.object(
            incheon_api_service,
            "get_flight_info",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        result = await flight_service.refresh_flight(mock_db, 1)

    assert result["changes_detected"] is False
    assert result["changes"] == []
    assert flight.gate_number == "114"
