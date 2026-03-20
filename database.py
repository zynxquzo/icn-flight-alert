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