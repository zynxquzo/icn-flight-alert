# main.py
"""
ICN Flight Alert API
인천공항 비행편 실시간 모니터링 및 알림 시스템
"""

import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

from database import run_alembic_on_app_startup
from flight_alert.routers.flight_router import router as flight_router
from flight_alert.routers.notification_router import router as notification_router
from flight_alert.routers.chatbot_router import router as chatbot_router
from flight_alert.routers.auth_router import router as auth_router
from flight_alert.routers.user_router import router as user_router
from flight_alert.exception_handlers import register_exception_handlers
from flight_alert.services.scheduler_service import flight_scheduler

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리"""
    # 서버 시작 시: (설정 시) Alembic 마이그레이션 적용 — RUN_ALEMBIC_ON_STARTUP 참고
    run_alembic_on_app_startup()
    
    # 스케줄러 시작 (10분 주기)
    flight_scheduler.start(interval_minutes=10)
    
    yield
    
    # 서버 종료 시: 스케줄러 중지
    flight_scheduler.stop()


app = FastAPI(
    title="ICN Flight Alert API",
    description="인천공항 비행편 실시간 모니터링 및 알림 시스템",
    version="1.0.0",
    lifespan=lifespan,
)

# 허용할 출처(프론트엔드 주소) 리스트
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,            # 허용할 도메인
    allow_credentials=True,           # 쿠키 포함 여부 (로그인 기능 시 중요)
    allow_methods=["*"],              # 모든 HTTP 메서드 허용 (GET, POST 등)
    allow_headers=["*"],              # 모든 HTTP 헤더 허용
)

# Exception Handler 등록
register_exception_handlers(app)

# 라우터 등록
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(flight_router)
app.include_router(notification_router)
app.include_router(chatbot_router)


@app.get("/", tags=["Health"])
async def health_check():
    """헬스 체크"""
    return {
        "status": "ok",
        "message": "ICN Flight Alert API가 실행 중입니다.",
        "docs": "/docs"
    }


@app.get("/health", tags=["Health"])
async def health():
    """헬스 체크 (간소화)"""
    return {"status": "healthy"}