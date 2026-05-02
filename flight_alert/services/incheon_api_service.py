# flight_alert/services/incheon_api_service.py
"""
Incheon Airport OpenAPI Service
인천공항 여객편 주간 운항 현황 API 연동 (httpx 비동기)
"""

import logging
import os
from datetime import date

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def _normalize_items(body: dict) -> list[dict]:
    """공공데이터 API 응답의 items를 항상 dict 리스트로 정규화"""
    raw = body.get("items")
    if raw is None:
        return []
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, dict):
        if "item" in raw:
            it = raw["item"]
            if isinstance(it, list):
                return [x for x in it if isinstance(x, dict)]
            if isinstance(it, dict):
                return [it]
        return [raw]
    return []


def _schedule_date_from_item(item: dict) -> date | None:
    """scheduleDateTime(YYYYMMDDHHmm…)에서 날짜 부분만 파싱"""
    s = item.get("scheduleDateTime")
    if not isinstance(s, str) or len(s) < 8:
        return None
    try:
        return date(int(s[0:4]), int(s[4:6]), int(s[6:8]))
    except ValueError:
        return None


class IncheonAPIService:
    """인천공항 OpenAPI 호출 서비스"""

    BASE_URL = "https://apis.data.go.kr/B551177/StatusOfPassengerFlightsDSOdp"
    API_KEY = os.getenv("INCHEON_AIRPORT_API_KEY")

    @classmethod
    async def get_flight_info(
        cls,
        flight_id: str,
        flight_date: date,
        flight_type: str,
        airport_code: str | None = None,
    ) -> dict | None:
        """비행편 정보 조회

        Args:
            flight_id: 항공편명 (예: "KE123", "RS704")
            flight_date: 날짜 (date 객체) — scheduleDateTime과 일치하는 행만 채택
            flight_type: "departure" or "arrival"
            airport_code: 공항 코드 (예: "NRT") - 선택

        Returns:
            dict: 비행편 정보 또는 None (에러/데이터 없음)
        """
        if flight_type == "departure":
            endpoint = "/getPassengerDeparturesDSOdp"
        elif flight_type == "arrival":
            endpoint = "/getPassengerArrivalsDSOdp"
        else:
            logger.error("잘못된 flight_type: %s", flight_type)
            return None

        params = {
            "serviceKey": cls.API_KEY,
            "type": "json",
            "numOfRows": 100,
            "pageNo": 1,
        }

        if airport_code:
            params["airport_code"] = airport_code

        url = f"{cls.BASE_URL}{endpoint}"
        logger.info(
            "인천공항 API 호출: %s, flight_id=%s, flight_date=%s",
            endpoint,
            flight_id,
            flight_date,
        )

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            if data["response"]["header"]["resultCode"] != "00":
                logger.error("API 에러: %s", data["response"]["header"]["resultMsg"])
                return None

            items = _normalize_items(data["response"]["body"])

            by_id = [
                item
                for item in items
                if item.get("flightId", "").upper() == flight_id.upper()
            ]

            by_date = [
                item for item in by_id if _schedule_date_from_item(item) == flight_date
            ]

            if by_date:
                flight_data = by_date[0]
            elif by_id:
                logger.warning(
                    "편명은 있으나 요청 날짜(%s)와 scheduleDateTime이 맞는 행이 없음: %s",
                    flight_date,
                    flight_id,
                )
                return None
            else:
                logger.warning("해당 편명을 찾을 수 없습니다: %s", flight_id)
                return None

            logger.info("비행편 정보 조회 성공: %s (%s)", flight_id, flight_date)
            return flight_data

        except httpx.HTTPError as e:
            logger.error("API 호출 실패: %s", e)
            return None
        except Exception as e:
            logger.error("예상치 못한 에러: %s", e)
            return None


incheon_api_service = IncheonAPIService()
