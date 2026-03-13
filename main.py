# main.py
"""
ICN Flight Alert API
인천공항 비행편 실시간 모니터링 및 알림 시스템
"""

from fastapi import FastAPI
from contextlib import asynccontextmanager

from database import engine
from flight_alert import models
from flight_alert.routers.flight_router import router as flight_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리"""
    # 서버 시작 시: 테이블 생성
    models.Base.metadata.create_all(bind=engine)
    yield
    # 서버 종료 시: 정리 작업 (필요시)
    pass


app = FastAPI(
    title="ICN Flight Alert API",
    description="인천공항 비행편 실시간 모니터링 및 알림 시스템",
    version="1.0.0",
    lifespan=lifespan,
)


# 라우터 등록
app.include_router(flight_router)


@app.get("/", tags=["Health"])
def health_check():
    """헬스 체크"""
    return {
        "status": "ok",
        "message": "ICN Flight Alert API가 실행 중입니다.",
        "docs": "/docs"
    }


@app.get("/health", tags=["Health"])
def health():
    """헬스 체크 (간소화)"""
    return {"status": "healthy"}