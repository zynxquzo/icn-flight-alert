"""인천공항 OpenAPI 파싱·조회 단위 테스트."""

from __future__ import annotations

from datetime import date

import re

import httpx
import pytest
import respx

from flight_alert.services.incheon_api_service import (
    IncheonAPIService,
    _normalize_items,
    _schedule_date_from_item,
)


class TestNormalizeItems:
    def test_none_returns_empty(self):
        assert _normalize_items({}) == []

    def test_list_of_dicts(self):
        body = {"items": [{"flightId": "KE1"}, {"flightId": "KE2"}]}
        assert len(_normalize_items(body)) == 2

    def test_single_item_wrapped(self):
        body = {"items": {"item": {"flightId": "KE123"}}}
        assert _normalize_items(body)[0]["flightId"] == "KE123"

    def test_item_list_wrapped(self):
        body = {"items": {"item": [{"flightId": "A"}, {"flightId": "B"}]}}
        assert len(_normalize_items(body)) == 2

    def test_bare_dict_item(self):
        body = {"items": {"flightId": "KE999"}}
        assert _normalize_items(body)[0]["flightId"] == "KE999"


class TestScheduleDateFromItem:
    def test_parses_yyyymmdd_from_schedule(self):
        item = {"scheduleDateTime": "20260522103000"}
        assert _schedule_date_from_item(item) == date(2026, 5, 22)

    def test_invalid_returns_none(self):
        assert _schedule_date_from_item({"scheduleDateTime": "bad"}) is None
        assert _schedule_date_from_item({}) is None


def _sample_api_response(items: list[dict]) -> dict:
    return {
        "response": {
            "header": {"resultCode": "00", "resultMsg": "OK"},
            "body": {"items": items},
        }
    }


@respx.mock
@pytest.mark.asyncio
async def test_get_flight_info_matches_id_and_date():
    item = {
        "flightId": "KE123",
        "scheduleDateTime": "202605221030",
        "gatenumber": "114",
        "airline": "대한항공",
    }
    route = respx.get(
        url=re.compile(r".*getPassengerDeparturesDSOdp")
    ).mock(return_value=httpx.Response(200, json=_sample_api_response([item])))

    result = await IncheonAPIService.get_flight_info(
        flight_id="ke123",
        flight_date=date(2026, 5, 22),
        flight_type="departure",
    )

    assert route.called
    assert result is not None
    assert result["flightId"] == "KE123"
    assert result["gatenumber"] == "114"


@respx.mock
@pytest.mark.asyncio
async def test_get_flight_info_wrong_date_returns_none():
    item = {
        "flightId": "KE123",
        "scheduleDateTime": "202605231030",
    }
    respx.get(url=re.compile(r".*getPassengerDeparturesDSOdp")).mock(
        return_value=httpx.Response(200, json=_sample_api_response([item]))
    )

    result = await IncheonAPIService.get_flight_info(
        flight_id="KE123",
        flight_date=date(2026, 5, 22),
        flight_type="departure",
    )
    assert result is None


@respx.mock
@pytest.mark.asyncio
async def test_get_flight_info_api_error_code():
    respx.get(url=re.compile(r".*getPassengerDeparturesDSOdp")).mock(
        return_value=httpx.Response(
            200,
            json={
                "response": {
                    "header": {"resultCode": "99", "resultMsg": "ERROR"},
                    "body": {},
                }
            },
        )
    )

    result = await IncheonAPIService.get_flight_info(
        flight_id="KE123",
        flight_date=date(2026, 5, 22),
        flight_type="departure",
    )
    assert result is None


@pytest.mark.asyncio
async def test_get_flight_info_invalid_flight_type():
    result = await IncheonAPIService.get_flight_info(
        flight_id="KE123",
        flight_date=date(2026, 5, 22),
        flight_type="invalid",
    )
    assert result is None
