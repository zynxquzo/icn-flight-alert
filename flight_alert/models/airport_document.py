# flight_alert/models/airport_document.py
"""
Airport RAG 문서
임베딩은 PostgreSQL native 의 double precision[] 로 저장합니다(pgvector 확장 불필요).
검색은 애플리케이션에서 코사인 유사도로 수행합니다(문서 수가 많아지면 pgvector 도입 권장).
"""

from datetime import datetime

from sqlalchemy import DateTime, Double, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class AirportDocument(Base):
    __tablename__ = "airport_documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    doc_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    subcategory: Mapped[str | None] = mapped_column(String(50), nullable=True)

    terminal: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    floor: Mapped[str | None] = mapped_column(String(20), nullable=True)
    zone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    area: Mapped[str | None] = mapped_column(String(100), nullable=True)
    gate_nearby: Mapped[str | None] = mapped_column(String(50), nullable=True)

    hours: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contact: Mapped[str | None] = mapped_column(String(100), nullable=True)
    price_range: Mapped[str | None] = mapped_column(String(50), nullable=True)

    content: Mapped[str] = mapped_column(Text, nullable=False)
    features: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    amenities: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)

    embedding: Mapped[list[float]] = mapped_column(ARRAY(Double), nullable=False)

    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
