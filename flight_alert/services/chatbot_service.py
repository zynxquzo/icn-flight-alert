# flight_alert/services/chatbot_service.py
"""
Chatbot Service
OpenAI를 사용한 공항 안내 챗봇
"""

import logging
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class ChatbotService:
    """OpenAI 기반 공항 안내 챗봇"""
    
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY가 설정되지 않았습니다")
            self.client = None
        else:
            self.client = OpenAI(api_key=api_key)
    
    def chat(
        self, 
        message: str, 
        terminal: str = "T1",
        wait_time_hours: int | None = None
    ) -> str:
        """챗봇과 대화
        
        Args:
            message: 사용자 메시지
            terminal: 터미널 (T1, T2)
            wait_time_hours: 대기 시간 (시간 단위)
        
        Returns:
            str: 챗봇 응답
        """
        if not self.client:
            return "죄송합니다. 챗봇 서비스가 현재 이용 불가능합니다."
        
        try:
            # 시스템 프롬프트 생성
            system_prompt = self._create_system_prompt(terminal, wait_time_hours)
            
            # OpenAI API 호출
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                temperature=0.7,
                max_tokens=500,
            )
            
            answer = response.choices[0].message.content
            logger.info(f"챗봇 응답 생성 성공: {len(answer)} 글자")
            
            return answer
            
        except Exception as e:
            logger.error(f"챗봇 응답 생성 실패: {e}")
            return "죄송합니다. 응답 생성 중 오류가 발생했습니다."
    
    def _create_system_prompt(
        self, 
        terminal: str, 
        wait_time_hours: int | None
    ) -> str:
        """시스템 프롬프트 생성"""
        
        base_prompt = """
당신은 인천국제공항 안내 도우미입니다.

역할:
- 공항에서 대기하는 승객들에게 유용한 정보 제공
- 식사, 쇼핑, 휴식 공간, 편의시설 추천
- 친절하고 간결하게 답변

주의사항:
- 구체적이고 실용적인 정보 제공
- 한국어로 답변
- 3-5문장으로 간결하게
- 이모지 적절히 사용 (✈️🍽️🛍️☕)
"""
        
        # 터미널 정보 추가
        terminal_info = f"\n현재 위치: 인천공항 {terminal}"
        
        # 대기 시간 정보 추가
        if wait_time_hours:
            time_info = f"\n대기 시간: 약 {wait_time_hours}시간"
            
            if wait_time_hours >= 3:
                time_info += "\n추천: 충분한 시간이 있으니 여유롭게 둘러보세요."
            elif wait_time_hours >= 1:
                time_info += "\n추천: 간단한 식사나 쇼핑을 즐기세요."
            else:
                time_info += "\n추천: 시간이 촉박하니 게이트 근처에서 대기하세요."
        else:
            time_info = ""
        
        return base_prompt + terminal_info + time_info


chatbot_service = ChatbotService()