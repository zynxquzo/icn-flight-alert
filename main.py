# main.py
"""
ICN Flight Alert API
인천공항 비행편 실시간 모니터링 및 알림 시스템
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import run_alembic_on_app_startup
from flight_alert.config import get_settings
from flight_alert.infrastructure.redis_client import close_redis
from flight_alert.logging_config import setup_logging
from flight_alert.middleware.request_id import RequestIdMiddleware, get_request_id
from flight_alert.observability.health import build_health_payload
from flight_alert.observability.sentry import init_sentry
from flight_alert.routers.auth_router import router as auth_router
from flight_alert.routers.chatbot_router import router as chatbot_router
from flight_alert.routers.flight_router import router as flight_router
from flight_alert.routers.notification_router import router as notification_router
from flight_alert.routers.user_router import router as user_router
from flight_alert.exception_handlers import register_exception_handlers
from flight_alert.services.scheduler_service import flight_scheduler

setup_logging()
init_sentry()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리"""
    run_alembic_on_app_startup()

    settings = get_settings()
    if settings.enable_scheduler:
        flight_scheduler.start(interval_minutes=settings.scheduler_interval_minutes)
    else:
        import logging

        logging.getLogger(__name__).info(
            "ENABLE_SCHEDULER=false: 주기적 비행편 갱신 스케줄러를 시작하지 않습니다."
        )

    yield

    flight_scheduler.stop()
    await close_redis()


app = FastAPI(
    title="ICN Flight Alert API",
    description="인천공항 비행편 실시간 모니터링 및 알림 시스템",
    version="1.0.0",
    lifespan=lifespan,
)

_default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
_origins_raw = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
origins = (
    [o.strip() for o in _origins_raw.split(",") if o.strip()]
    if _origins_raw
    else _default_origins
)

app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

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
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health():
    """헬스 체크 — DB·Redis·스케줄러 상태 포함"""
    payload = await build_health_payload()
    rid = get_request_id()
    if rid:
        payload["request_id"] = rid
    return payload
