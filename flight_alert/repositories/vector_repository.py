# flight_alert/repositories/vector_repository.py
"""airport_documents 저장 및 검색 — PostgreSQL(배열+코사인) 또는 ChromaDB."""

from __future__ import annotations

import math
import os
from datetime import datetime, timezone
from typing import Any, Optional, Union

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from flight_alert.models.airport_document import AirportDocument

AirportDocLike = Union[AirportDocument, Any]


def use_chroma_backend() -> bool:
    return os.getenv("VECTOR_BACKEND", "postgres").strip().lower() in ("chroma",)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b, strict=True):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


async def upsert_document(
    db: AsyncSession | None, payload: dict[str, Any]
) -> AirportDocLike:
    """doc_id 기준 삽입/갱신. Chroma 모드에서는 db 미사용."""
    if use_chroma_backend():
        from flight_alert.repositories.chroma_rag_store import chroma_upsert_document

        return chroma_upsert_document(payload)

    if db is None:
        raise ValueError("PostgreSQL 모드에서는 db 세션이 필요합니다")
    doc_id = payload["doc_id"]
    now = datetime.now(timezone.utc)
    existing = await db.scalar(
        select(AirportDocument).where(AirportDocument.doc_id == doc_id)
    )
    if existing:
        for key, value in payload.items():
            if key == "doc_id":
                continue
            setattr(existing, key, value)
        existing.updated_at = now
        await db.flush()
        return existing
    row = AirportDocument(**payload)
    db.add(row)
    await db.flush()
    return row


async def count_documents(db: AsyncSession | None) -> int:
    if use_chroma_backend():
        from flight_alert.repositories.chroma_rag_store import chroma_count_documents

        return chroma_count_documents()
    if db is None:
        raise ValueError("PostgreSQL 모드에서는 db 세션이 필요합니다")
    result = await db.execute(select(func.count()).select_from(AirportDocument))
    return int(result.scalar_one() or 0)


async def search_similar_documents(
    db: AsyncSession | None,
    query_embedding: list[float],
    *,
    top_k: int = 5,
    category: Optional[str] = None,
    terminal: Optional[str] = None,
) -> list[AirportDocLike]:
    if use_chroma_backend():
        from flight_alert.repositories.chroma_rag_store import chroma_search_similar

        return chroma_search_similar(
            query_embedding,
            top_k=top_k,
            category=category,
            terminal=terminal,
        )

    if db is None:
        raise ValueError("PostgreSQL 모드에서는 db 세션이 필요합니다")
    stmt = select(AirportDocument)
    if category:
        stmt = stmt.where(AirportDocument.category == category)
    if terminal:
        stmt = stmt.where(AirportDocument.terminal == terminal)
    result = await db.execute(stmt)
    rows = list(result.scalars().all())
    scored: list[tuple[float, AirportDocument]] = []
    for row in rows:
        emb = row.embedding
        if not emb:
            continue
        sim = _cosine_similarity(query_embedding, list(emb))
        scored.append((sim, row))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [r for _, r in scored[:top_k]]


async def get_document_by_id(
    db: AsyncSession | None, doc_id: str
) -> AirportDocLike | None:
    if use_chroma_backend():
        from flight_alert.repositories.chroma_rag_store import chroma_get_document

        return chroma_get_document(doc_id)
    if db is None:
        raise ValueError("PostgreSQL 모드에서는 db 세션이 필요합니다")
    return await db.scalar(
        select(AirportDocument).where(AirportDocument.doc_id == doc_id)
    )


async def list_distinct_categories(db: AsyncSession | None) -> list[str]:
    if use_chroma_backend():
        from flight_alert.repositories.chroma_rag_store import chroma_list_categories

        return chroma_list_categories()
    if db is None:
        raise ValueError("PostgreSQL 모드에서는 db 세션이 필요합니다")
    result = await db.execute(select(AirportDocument.category).distinct())
    rows = result.scalars().all()
    return sorted({r for r in rows if r})


async def search_keyword_documents(
    db: AsyncSession | None,
    query: str,
    *,
    top_k: int = 8,
    category: Optional[str] = None,
    terminal: Optional[str] = None,
) -> list[AirportDocLike]:
    if use_chroma_backend():
        from flight_alert.repositories.chroma_rag_store import chroma_search_keyword

        return chroma_search_keyword(
            query,
            top_k=top_k,
            category=category,
            terminal=terminal,
        )

    if db is None:
        raise ValueError("PostgreSQL 모드에서는 db 세션이 필요합니다")
    q = (query or "").strip()
    if len(q) < 2:
        return []
    pattern = f"%{q}%"
    stmt = select(AirportDocument).where(
        or_(
            AirportDocument.title.ilike(pattern),
            AirportDocument.content.ilike(pattern),
        )
    )
    if category:
        stmt = stmt.where(AirportDocument.category == category)
    if terminal:
        stmt = stmt.where(AirportDocument.terminal == terminal)
    stmt = stmt.limit(top_k)
    result = await db.execute(stmt)
    return list(result.scalars().all())
