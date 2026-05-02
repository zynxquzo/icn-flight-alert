# database.py
"""
Database Configuration
PostgreSQL 연결 설정 (SQLAlchemy 2 async + asyncpg)
"""

import logging
import os
from collections.abc import AsyncGenerator

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

load_dotenv()

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool) -> bool:
    """환경 변수를 true/false로 해석. 미설정 시 default."""
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def normalize_database_url_to_async(url: str) -> str:
    """postgresql:// … → postgresql+asyncpg:// …"""
    if "+asyncpg" in url:
        return url
    u = url.replace("postgresql+psycopg2://", "postgresql://", 1)
    if u.startswith("postgresql://"):
        return "postgresql+asyncpg://" + u[len("postgresql://") :]
    raise ValueError(
        "DATABASE_URL은 PostgreSQL 연결 문자열이어야 합니다 (postgresql:// 또는 postgresql+asyncpg://)."
    )


def normalize_database_url_to_sync_psycopg2(url: str) -> str:
    """Alembic·psycopg2 스크립트용: postgresql+asyncpg:// → postgresql+psycopg2://"""
    if "+asyncpg" in url:
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    return url


# PostgreSQL 연결 URL
_DATABASE_URL_RAW = os.getenv("DATABASE_URL")

if not _DATABASE_URL_RAW:
    raise ValueError("DATABASE_URL 환경 변수가 설정되지 않았습니다")

DATABASE_URL = normalize_database_url_to_async(_DATABASE_URL_RAW)

# SQLAlchemy 비동기 엔진
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


# SQLAlchemy 2.0 스타일의 Base 클래스 선언
class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 의존성: 비동기 DB 세션 제공"""
    async with async_session_maker() as session:
        yield session


def run_alembic_upgrade() -> None:
    """Alembic을 head까지 적용합니다. 앱·스크립트 기동 시 DB 스키마를 맞출 때 사용합니다."""
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    root = Path(__file__).resolve().parent
    ini = root / "alembic.ini"
    if not ini.is_file():
        raise FileNotFoundError(f"Alembic 설정을 찾을 수 없습니다: {ini}")
    cfg = Config(str(ini))
    command.upgrade(cfg, "head")


def run_alembic_on_app_startup() -> None:
    """FastAPI 앱 기동(lifespan)에서만 사용. RUN_ALEMBIC_ON_STARTUP=false이면 생략.

    다중 인스턴스·오토스케일 환경에서는 동시에 upgrade가 겹칠 수 있으므로,
    배포 파이프라인에서만 `alembic upgrade head`를 실행하고 이 함수는 끄는 것을 권장합니다.
    """
    if not _env_bool("RUN_ALEMBIC_ON_STARTUP", default=True):
        logger.info(
            "RUN_ALEMBIC_ON_STARTUP=false: 기동 시 Alembic 마이그레이션을 건너뜁니다. "
            "DB는 배포 전 `uv run alembic upgrade head` 등으로 맞춰 두었는지 확인하세요."
        )
        return
    run_alembic_upgrade()
