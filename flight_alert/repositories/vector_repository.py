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
    """doc_id 기준 삽입/갱신. content_hash가 동일하면 임베딩·내용 업데이트 생략.

    Chroma 모드에서는 db 미사용.
    """
    if use_chroma_backend():
        from flight_alert.repositories.chroma_rag_store import chroma_upsert_document

        return chroma_upsert_document(payload)

    if db is None:
        raise ValueError("PostgreSQL 모드에서는 db 세션이 필요합니다")
    doc_id = payload["doc_id"]
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    existing = await db.scalar(
        select(AirportDocument).where(AirportDocument.doc_id == doc_id)
    )
    if existing:
        new_hash = payload.get("content_hash")
        # content_hash가 있고 동일하면 임베딩 재생성 불필요 → 메타만 갱신
        if new_hash and existing.content_hash == new_hash:
            for key in ("source_url", "source_type", "hours", "contact", "price_range"):
                if key in payload:
                    setattr(existing, key, payload[key])
            existing.updated_at = now
            await db.flush()
            return existing
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


async def search_hybrid_documents(
    db: AsyncSession | None,
    query_embedding: list[float],
    query_text: str,
    *,
    top_k: int = 6,
    vector_weight: float = 0.65,
    keyword_weight: float = 0.35,
    category: Optional[str] = None,
    terminal: Optional[str] = None,
) -> list[AirportDocLike]:
    """벡터 유사도 + 키워드 ILIKE 가중 합산 하이브리드 검색.

    PostgreSQL ARRAY(Double) 코사인 계산과 ILIKE 히트 여부를 조합합니다.
    ChromaDB 모드에서는 벡터 검색 결과를 그대로 반환합니다.
    """
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

    q_text = (query_text or "").strip()
    pattern = f"%{q_text}%" if len(q_text) >= 2 else None

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
        vec_score = _cosine_similarity(query_embedding, list(emb)) if emb else 0.0

        kw_score = 0.0
        if pattern:
            title = (row.title or "").lower()
            content = (row.content or "").lower()
            p_lower = q_text.lower()
            if p_lower in title:
                kw_score = 1.0
            elif p_lower in content:
                kw_score = 0.6

        combined = vec_score * vector_weight + kw_score * keyword_weight
        scored.append((combined, row))

    scored.sort(key=lambda t: t[0], reverse=True)
    return [r for _, r in scored[:top_k]]
