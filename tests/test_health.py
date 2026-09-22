"""헬스체크 스케줄러 상태 판정 회귀 테스트.

check_scheduler()에서 연산자 우선순위 버그(6c3e5f8)와 TTL 버그(a1c65e8)가
연이어 발생했으나 회귀 테스트가 없었다 — 재발 방지용 단위 테스트.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from flight_alert.observability.health import check_scheduler
from flight_alert.services.scheduler_service import FlightScheduler


def _settings(**overrides):
    settings = MagicMock()
    settings.enable_scheduler = True
    settings.scheduler_leader_lock = False
    settings.redis_enabled = False
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


@pytest.mark.asyncio
class TestCheckScheduler:
    async def test_disabled_scheduler_is_ok_even_with_stale_error(self):
        """스케줄러 비활성화 상태면 last_run_status가 'error'로 남아있어도 unhealthy로 오탐하면 안 됨."""
        settings = _settings(enable_scheduler=False)
        info = {
            "running": False,
            "last_run_status": "error",
            "cleanup_last_run_status": "error",
        }
        with (
            patch(
                "flight_alert.observability.health.get_settings", return_value=settings
            ),
            patch(
                "flight_alert.observability.health.flight_scheduler.get_status",
                return_value=info,
            ),
        ):
            result = await check_scheduler(is_leader=True)

        assert result["status"] == "ok"

    async def test_enabled_scheduler_not_running_is_fail(self):
        settings = _settings(enable_scheduler=True)
        info = {
            "running": False,
            "last_run_status": None,
            "cleanup_last_run_status": None,
        }
        with (
            patch(
                "flight_alert.observability.health.get_settings", return_value=settings
            ),
            patch(
                "flight_alert.observability.health.flight_scheduler.get_status",
                return_value=info,
            ),
        ):
            result = await check_scheduler(is_leader=True)

        assert result["status"] == "fail"

    async def test_enabled_scheduler_running_ok_is_ok(self):
        settings = _settings(enable_scheduler=True)
        info = {
            "running": True,
            "last_run_status": "ok",
            "cleanup_last_run_status": "ok",
        }
        with (
            patch(
                "flight_alert.observability.health.get_settings", return_value=settings
            ),
            patch(
                "flight_alert.observability.health.flight_scheduler.get_status",
                return_value=info,
            ),
        ):
            result = await check_scheduler(is_leader=True)

        assert result["status"] == "ok"


class _FakeScalarsResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _FakeSession:
    def __init__(self, flights):
        self._flights = flights

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False

    async def scalars(self, _stmt):
        return _FakeScalarsResult(self._flights)

    async def rollback(self):
        pass


@pytest.mark.asyncio
class TestRefreshActiveFlights:
    """개별 비행편 갱신이 전부 실패해도 job 상태가 'ok'로 오기록되던 버그 회귀 테스트."""

    async def test_all_flights_failing_records_error_status(self):
        flight = MagicMock(flight_pk=1, flight_id="KE123")
        scheduler = FlightScheduler()

        with (
            patch(
                "flight_alert.services.scheduler_leader.get_settings",
                return_value=_settings(),
            ),
            patch("database.async_session_maker", return_value=_FakeSession([flight])),
            patch(
                "flight_alert.services.flight_service.flight_service.refresh_flight",
                new=AsyncMock(side_effect=RuntimeError("api down")),
            ),
        ):
            await scheduler._refresh_active_flights_async()

        assert scheduler._last_run_status == "error"

    async def test_some_flights_failing_still_records_ok(self):
        ok_flight = MagicMock(flight_pk=1, flight_id="KE123")
        fail_flight = MagicMock(flight_pk=2, flight_id="KE456")
        scheduler = FlightScheduler()

        async def _refresh_side_effect(_db, flight_pk):
            if flight_pk == fail_flight.flight_pk:
                raise RuntimeError("api down")
            return {"changes_detected": False, "changes": []}

        with (
            patch(
                "flight_alert.services.scheduler_leader.get_settings",
                return_value=_settings(),
            ),
            patch(
                "database.async_session_maker",
                return_value=_FakeSession([ok_flight, fail_flight]),
            ),
            patch(
                "flight_alert.services.flight_service.flight_service.refresh_flight",
                new=AsyncMock(side_effect=_refresh_side_effect),
            ),
        ):
            await scheduler._refresh_active_flights_async()

        assert scheduler._last_run_status == "ok"
