# database.py
"""
Database Configuration
PostgreSQL 연결 설정
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv

load_dotenv()

# PostgreSQL 연결 URL
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL 환경 변수가 설정되지 않았습니다")

# SQLAlchemy 엔진 생성
engine = create_engine(
    DATABASE_URL,
    echo=False,  # SQL 로그 출력 (개발 시 True로 설정 가능)
    pool_pre_ping=True,  # 연결 유효성 확인
)

# 세션 팩토리
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# SQLAlchemy 2.0 스타일의 Base 클래스 선언
class Base(DeclarativeBase):
    pass


# Dependency for FastAPI
def get_db():
    """FastAPI 의존성: DB 세션 제공"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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