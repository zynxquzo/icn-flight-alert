# flight_alert/services/email_service.py
"""
Email Service
Gmail SMTP를 사용한 이메일 발송
"""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class EmailService:
    """이메일 발송 서비스"""
    
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
    SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL")
    
    @classmethod
    def send_notification_email(
        cls,
        to_email: str,
        subject: str,
        message: str,
        flight_id: str = None,
    ) -> bool:
        """비행편 알림 이메일 발송
        
        Args:
            to_email: 받는 사람 이메일
            subject: 이메일 제목
            message: 이메일 본문
            flight_id: 비행편명 (선택)
        
        Returns:
            bool: 발송 성공 여부
        """
        # 환경 변수 확인
        if not all([cls.SMTP_USERNAME, cls.SMTP_PASSWORD, cls.SMTP_FROM_EMAIL]):
            logger.error("SMTP 환경 변수가 설정되지 않았습니다")
            return False
        
        try:
            # 이메일 메시지 생성
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = cls.SMTP_FROM_EMAIL
            msg['To'] = to_email
            
            # HTML 본문 생성
            html_body = cls._create_html_body(message, flight_id)
            
            # 텍스트 버전과 HTML 버전 추가
            text_part = MIMEText(message, 'plain', 'utf-8')
            html_part = MIMEText(html_body, 'html', 'utf-8')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # SMTP 서버 연결 및 발송
            with smtplib.SMTP(cls.SMTP_HOST, cls.SMTP_PORT) as server:
                server.starttls()  # TLS 암호화
                server.login(cls.SMTP_USERNAME, cls.SMTP_PASSWORD)
                server.send_message(msg)
            
            logger.info("✅ 이메일 발송 성공: to=%s, subject=%s", to_email, subject)
            return True
            
        except smtplib.SMTPAuthenticationError:
            logger.error("❌ SMTP 인증 실패 - 이메일/비밀번호 확인 필요")
            return False
        
        except smtplib.SMTPException as e:
            logger.error("❌ SMTP 에러: %s", e)
            return False
        
        except Exception as e:
            logger.error("❌ 이메일 발송 실패: %s", e, exc_info=True)
            return False

    @classmethod
    def send_simple_email(
        cls,
        to_email: str,
        subject: str,
        text_body: str,
        html_inner: str | None = None,
    ) -> bool:
        """인증·재설정 등 단문 메일 (SMTP 미설정 시 False)."""
        if not all([cls.SMTP_USERNAME, cls.SMTP_PASSWORD, cls.SMTP_FROM_EMAIL]):
            logger.error("SMTP 환경 변수가 설정되지 않았습니다")
            return False
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = cls.SMTP_FROM_EMAIL
            msg["To"] = to_email
            msg.attach(MIMEText(text_body, "plain", "utf-8"))
            if html_inner:
                wrapped = f"""<html><body style="font-family:Segoe UI,Arial,sans-serif;line-height:1.6">
{html_inner}
<p style="color:#666;font-size:12px;margin-top:24px">ICN Flight Alert</p>
</body></html>"""
                msg.attach(MIMEText(wrapped, "html", "utf-8"))
            with smtplib.SMTP(cls.SMTP_HOST, cls.SMTP_PORT) as server:
                server.starttls()
                server.login(cls.SMTP_USERNAME, cls.SMTP_PASSWORD)
                server.send_message(msg)
            logger.info("✅ 단문 이메일 발송 성공: to=%s subject=%s", to_email, subject)
            return True
        except Exception as e:
            logger.error("❌ 단문 이메일 발송 실패: %s", e, exc_info=True)
            return False

    @classmethod
    def _create_html_body(cls, message: str, flight_id: str = None) -> str:
        """HTML 이메일 본문 생성"""
        flight_info = f"<p><strong>항공편:</strong> {flight_id}</p>" if flight_id else ""
        
        html = f"""
        <html>
            <head>
                <style>
                    body {{
                        font-family: 'Segoe UI', Arial, sans-serif;
                        line-height: 1.6;
                        color: #333;
                    }}
                    .container {{
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                        background-color: #f9f9f9;
                        border-radius: 10px;
                    }}
                    .header {{
                        background-color: #4CAF50;
                        color: white;
                        padding: 20px;
                        text-align: center;
                        border-radius: 10px 10px 0 0;
                    }}
                    .content {{
                        background-color: white;
                        padding: 30px;
                        border-radius: 0 0 10px 10px;
                    }}
                    .message {{
                        font-size: 16px;
                        margin: 20px 0;
                        padding: 15px;
                        background-color: #fffbea;
                        border-left: 4px solid #ffc107;
                        border-radius: 5px;
                    }}
                    .footer {{
                        text-align: center;
                        margin-top: 20px;
                        font-size: 12px;
                        color: #777;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h2>✈️ 인천공항 비행편 알림</h2>
                    </div>
                    <div class="content">
                        {flight_info}
                        <div class="message">
                            {message}
                        </div>
                        <p>안전한 여행 되세요!</p>
                        <div class="footer">
                            <p>ICN Flight Alert System</p>
                            <p>이 메일은 자동으로 발송되었습니다.</p>
                        </div>
                    </div>
                </div>
            </body>
        </html>
        """
        return html


email_service = EmailService()