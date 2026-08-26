"""공유 링크 응답 스키마가 소유자 개인정보를 노출하지 않는지 확인."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from flight_alert.models.flight import Flight
from flight_alert.schemas.flight import SharedFlightResponse


def _make_flight(**overrides) -> Flight:
    defaults = dict(
        flight_pk=1,
        user_id=1,
        user_email="owner@example.com",
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
        share_token="abc123",
    )
    defaults.update(overrides)
    return Flight(**defaults)


def test_shared_flight_response_excludes_owner_pii():
    flight = _make_flight()
    payload = SharedFlightResponse.model_validate(flight).model_dump()

    assert "user_id" not in payload
    assert "user_email" not in payload
    assert "share_token" not in payload
    assert payload["flight_id"] == "KE123"
    assert payload["gate_number"] == "114"
