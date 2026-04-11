# flight_alert/services/crawler_service.py
"""인천공항 공식 사이트 HTML 수집 (httpx 비동기)"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}

# 편의 · 공공시설 (공식 사이트: fnctId=facilityInfo, fnctNo=25 — 제1/제2 등은 본문·필터로 구분)
FACILITY_BASE = "https://www.airport.kr/ap_ko/1008/subview.do"
FACILITY_FNCT_NO = "25"

FOOD_LIST_URL = "https://www.airport.kr/ap_ko/food/list.do"
SHOPPING_URL = "https://www.airport.kr/ap_ko/shop/list.do"

# 교통·절차는 상세 페이지가 분산되어 있어 URL 상수만 제공 (필요 시 확장)
TRANSPORT_AREX = "https://www.airport.kr/ap_ko/transport/train/trainInfo.do"
PROCEDURE_DEPARTURE = "https://www.airport.kr/ap_ko/guide/departure/depcheck.do"


async def _fetch(url: str, params: dict[str, str] | None = None) -> str:
    async with httpx.AsyncClient(
        headers=DEFAULT_HEADERS, follow_redirects=True, timeout=60.0
    ) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        # httpx Response에는 requests의 apparent_encoding 이 없음 — .text 가 charset 우선 디코딩
        return r.text


async def crawl_airport_facilities(
    terminal_key: str = "T1",
) -> tuple[str, str]:
    """편의 · 공공시설 페이지 HTML과 요청 URL 문자열을 반환.

    terminal_key는 호환용 인자이며, 현재 목록 URL은 fnctNo=25 단일 소스를 사용합니다.
    """
    _ = terminal_key
    params = {"fnctId": "facilityInfo", "fnctNo": FACILITY_FNCT_NO}
    url = f"{FACILITY_BASE}?fnctId={params['fnctId']}&fnctNo={params['fnctNo']}"
    html = await _fetch(FACILITY_BASE, params=params)
    return html, url


async def crawl_airport_food() -> tuple[str, str]:
    """식음료 목록 페이지."""
    html = await _fetch(FOOD_LIST_URL)
    return html, FOOD_LIST_URL


async def crawl_airport_shopping() -> tuple[str, str]:
    """쇼핑 목록 페이지 (일반/면세 등)."""
    html = await _fetch(SHOPPING_URL)
    return html, SHOPPING_URL


async def crawl_url(url: str, params: dict[str, Any] | None = None) -> tuple[str, str]:
    """임의 URL 크롤링."""
    html = await _fetch(url, params=params or {})
    return html, url
