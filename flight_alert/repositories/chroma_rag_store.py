# flight_alert/repositories/chroma_rag_store.py
"""
ChromaDB 영속 저장소 — RAG 문서(임베딩·메타) 전용.
PostgreSQL의 users/flights 등과 분리; VECTOR_BACKEND=chroma 일 때 사용.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_DIR = Path(__file__).resolve().parents[2] / ".chroma_airport"
_COLLECTION_NAME = "airport_documents"

_client: Any = None
_collection: Any = None


def _persist_path() -> str:
    return os.getenv("CHROMA_PERSIST_DIR", str(_DEFAULT_DIR))


def _collection_name() -> str:
    return os.getenv("CHROMA_COLLECTION", _COLLECTION_NAME).strip() or _COLLECTION_NAME


def _get_collection():
    global _client, _collection
    if _collection is not None:
        return _collection
    import chromadb
    from chromadb.config import Settings

    path = _persist_path()
    Path(path).mkdir(parents=True, exist_ok=True)
    _client = chromadb.PersistentClient(
        path=path,
        settings=Settings(anonymized_telemetry=False),
    )
    _collection = _client.get_or_create_collection(
        name=_collection_name(),
        metadata={"hnsw:space": "cosine"},
    )
    logger.info("Chroma 컬렉션 준비: path=%s name=%s", path, _collection_name())
    return _collection


@dataclass
class AirportDocView:
    """ORM AirportDocument 과 동일 필드(에이전트·챗봇에서 공통 사용)."""

    doc_id: str
    title: str
    category: str
    subcategory: str | None = None
    terminal: str | None = None
    floor: str | None = None
    zone: str | None = None
    area: str | None = None
    gate_nearby: str | None = None
    hours: str | None = None
    contact: str | None = None
    price_range: str | None = None
    content: str = ""
    features: list[str] | None = None
    amenities: list[str] | None = None
    source_url: str | None = None
    source_type: str | None = None


def _s(meta: dict[str, Any], key: str) -> str | None:
    v = meta.get(key)
    if v is None or v == "":
        return None
    return str(v)


def _view_from_record(doc_id: str, meta: dict[str, Any], document: str) -> AirportDocView:
    feats_raw = meta.get("features_json") or "[]"
    amen_raw = meta.get("amenities_json") or "[]"
    try:
        features = json.loads(feats_raw) if isinstance(feats_raw, str) else None
        if not isinstance(features, list):
            features = None
    except json.JSONDecodeError:
        features = None
    try:
        amenities = json.loads(amen_raw) if isinstance(amen_raw, str) else None
        if not isinstance(amenities, list):
            amenities = None
    except json.JSONDecodeError:
        amenities = None
    return AirportDocView(
        doc_id=doc_id,
        title=_s(meta, "title") or "",
        category=_s(meta, "category") or "rest",
        subcategory=_s(meta, "subcategory"),
        terminal=_s(meta, "terminal"),
        floor=_s(meta, "floor"),
        zone=_s(meta, "zone"),
        area=_s(meta, "area"),
        gate_nearby=_s(meta, "gate_nearby"),
        hours=_s(meta, "hours"),
        contact=_s(meta, "contact"),
        price_range=_s(meta, "price_range"),
        content=document or (_s(meta, "content_preview") or ""),
        features=features,
        amenities=amenities,
        source_url=_s(meta, "source_url"),
        source_type=_s(meta, "source_type"),
    )


def _meta_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Chroma 메타데이터는 str/int/float/bool 만 허용."""
    md: dict[str, Any] = {}
    for key in (
        "title",
        "category",
        "subcategory",
        "terminal",
        "floor",
        "zone",
        "area",
        "gate_nearby",
        "hours",
        "contact",
        "price_range",
        "source_url",
        "source_type",
    ):
        v = payload.get(key)
        md[key] = "" if v is None else str(v)[:8190]
    md["features_json"] = json.dumps(payload.get("features") or [], ensure_ascii=False)[:8190]
    md["amenities_json"] = json.dumps(payload.get("amenities") or [], ensure_ascii=False)[:8190]
    content = (payload.get("content") or "")[:50000]
    md["content_preview"] = content[:2000]
    return md


def chroma_upsert_document(payload: dict[str, Any]) -> AirportDocView:
    col = _get_collection()
    doc_id = payload["doc_id"]
    meta = _meta_from_payload(payload)
    content = payload.get("content") or ""
    col.upsert(
        ids=[doc_id],
        embeddings=[list(payload["embedding"])],
        metadatas=[meta],
        documents=[content],
    )
    return _view_from_record(doc_id, meta, content)


def chroma_count_documents() -> int:
    return int(_get_collection().count())


def chroma_search_similar(
    query_embedding: list[float],
    *,
    top_k: int = 5,
    category: str | None = None,
    terminal: str | None = None,
) -> list[AirportDocView]:
    col = _get_collection()
    if col.count() == 0:
        return []
    where: dict[str, Any] | None = None
    conds: list[dict[str, Any]] = []
    if category:
        conds.append({"category": category})
    if terminal:
        conds.append({"terminal": terminal})
    if len(conds) == 1:
        where = conds[0]
    elif len(conds) > 1:
        where = {"$and": conds}

    n = max(1, min(top_k, max(1, col.count())))
    try:
        res = col.query(
            query_embeddings=[list(query_embedding)],
            n_results=n,
            where=where,
            include=["metadatas", "documents", "distances"],
        )
    except Exception as e:
        logger.warning("Chroma query 실패: %s", e, exc_info=True)
        return []
    ids = (res.get("ids") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    docs = (res.get("documents") or [[]])[0]
    out: list[AirportDocView] = []
    for i, doc_id in enumerate(ids):
        meta = metas[i] if i < len(metas) else {}
        doc = docs[i] if i < len(docs) else ""
        out.append(_view_from_record(doc_id, meta or {}, doc or ""))
    return out


def chroma_get_document(doc_id: str) -> AirportDocView | None:
    col = _get_collection()
    r = col.get(ids=[doc_id], include=["metadatas", "documents"])
    ids = r.get("ids") or []
    if not ids:
        return None
    meta = (r.get("metadatas") or [None])[0] or {}
    doc = (r.get("documents") or [None])[0] or ""
    return _view_from_record(ids[0], meta, doc)


def chroma_list_categories() -> list[str]:
    col = _get_collection()
    if col.count() == 0:
        return []
    r = col.get(include=["metadatas"], limit=min(50_000, max(1, col.count())))
    metas = r.get("metadatas") or []
    cats = {m.get("category") for m in metas if m and m.get("category")}
    return sorted(c for c in cats if c)


def chroma_search_keyword(
    query: str,
    *,
    top_k: int = 8,
    category: str | None = None,
    terminal: str | None = None,
) -> list[AirportDocView]:
    col = _get_collection()
    q = (query or "").strip()
    if len(q) < 2:
        return []
    try:
        r = col.get(where_document={"$contains": q}, include=["metadatas", "documents"])
    except Exception as e:
        logger.warning("Chroma where_document 검색 실패, 부분 스캔으로 폴백: %s", e, exc_info=True)
        cap = min(8000, max(1, col.count()))
        r = col.get(include=["metadatas", "documents"], limit=cap)
    ids = r.get("ids") or []
    metas = r.get("metadatas") or []
    docs = r.get("documents") or []
    out: list[AirportDocView] = []
    for i, doc_id in enumerate(ids):
        meta = metas[i] if i < len(metas) else {}
        doc = docs[i] if i < len(docs) else ""
        v = _view_from_record(doc_id, meta or {}, doc or "")
        if category and (v.category or "") != category:
            continue
        if terminal and (v.terminal or "") != terminal:
            continue
        if q.lower() not in (v.title + v.content).lower():
            continue
        out.append(v)
        if len(out) >= top_k:
            break
    return out[:top_k]
