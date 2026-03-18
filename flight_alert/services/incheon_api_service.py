# flight_alert/services/incheon_api_service.py
"""
Incheon Airport OpenAPI Service
인천공항 여객편 주간 운항 현황 API 연동
"""

import logging
import requests
import os
from datetime import date
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class IncheonAPIService:
    """인천공항 OpenAPI 호출 서비스"""
    
    BASE_URL = "https://apis.data.go.kr/B551177/StatusOfPassengerFlightsDSOdp"
    API_KEY = os.getenv("INCHEON_AIRPORT_API_KEY")
    
    @classmethod
    def get_flight_info(
        cls, 
        flight_id: str, 
        flight_date: date, 
        flight_type: str,
        airport_code: str | None = None
    ) -> dict | None:
        """비행편 정보 조회
        
        Args:
            flight_id: 항공편명 (예: "KE123", "RS704")
            flight_date: 날짜 (date 객체)
            flight_type: "departure" or "arrival"
            airport_code: 공항 코드 (예: "NRT") - 선택
        
        Returns:
            dict: 비행편 정보 또는 None (에러/데이터 없음)
        """
        # 엔드포인트 결정
        if flight_type == "departure":
            endpoint = "/getPassengerDeparturesDSOdp"
        elif flight_type == "arrival":
            endpoint = "/getPassengerArrivalsDSOdp"
        else:
            logger.error(f"잘못된 flight_type: {flight_type}")
            return None
        
        # 파라미터 설정
        params = {
            "serviceKey": cls.API_KEY,
            "type": "json",
            "numOfRows": 100,  # 많이 조회해서 필터링
            "pageNo": 1,
        }
        
        # airport_code가 있으면 추가
        if airport_code:
            params["airport_code"] = airport_code
        
        try:
            # API 호출
            url = f"{cls.BASE_URL}{endpoint}"
            logger.info(f"인천공항 API 호출: {endpoint}, flight_id={flight_id}")
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # 응답 확인
            if data["response"]["header"]["resultCode"] != "00":
                logger.error(f"API 에러: {data['response']['header']['resultMsg']}")
                return None
            
            # items에서 해당 편명 찾기
            items = data["response"]["body"].get("items", [])
            
            # flight_id로 필터링 (대소문자 무시)
            matching_flights = [
                item for item in items 
                if item.get("flightId", "").upper() == flight_id.upper()
            ]
            
            if not matching_flights:
                logger.warning(f"해당 편명을 찾을 수 없습니다: {flight_id}")
                return None
            
            # 첫 번째 매칭 결과 반환
            flight_data = matching_flights[0]
            logger.info(f"비행편 정보 조회 성공: {flight_id}")
            
            return flight_data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API 호출 실패: {e}")
            return None
        except Exception as e:
            logger.error(f"예상치 못한 에러: {e}")
            return None


incheon_api_service = IncheonAPIService()