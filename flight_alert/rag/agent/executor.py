# flight_alert/rag/agent/executor.py
"""에이전트 도구 실행기 (DB + 임베딩)."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from flight_alert.repositories import vector_repository
from flight_alert.repositories.vector_repository import search_hybrid_documents
from flight_alert.services.embedding_service import generate_embedding

logger = logging.getLogger(__name__)

_MAX_CONTENT_CHARS = 1200


def _doc_public_dict(doc: Any) -> dict[str, Any]:
    content = (doc.content or "")[:_MAX_CONTENT_CHARS]
    feats = doc.features if doc.features else []
    return {
        "doc_id": doc.doc_id,
        "title": doc.title,
        "category": doc.category,
        "subcategory": doc.subcategory,
        "terminal": doc.terminal,
        "floor": doc.floor,
        "zone": doc.zone,
        "area": doc.area,
        "gate_nearby": doc.gate_nearby,
        "hours": doc.hours,
        "contact": doc.contact,
        "price_range": doc.price_range,
        "content": content,
        "features": list(feats) if feats else None,
        "source_url": doc.source_url,
    }


def _parse_bool(v: Any, default: bool = False) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return default
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "on")
    return default


def _parse_int(v: Any, default: int, lo: int, hi: int) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        n = default
    return max(lo, min(hi, n))


async def execute_agent_tool(
    db: AsyncSession,
    name: str,
    arguments_json: str,
    *,
    default_terminal: str,
) -> tuple[str, list[dict[str, Any]]]:
    """도구 실행. 반환: (JSON 문자열, 출처 메타 리스트)."""
    try:
        args: dict[str, Any] = json.loads(arguments_json or "{}")
    except json.JSONDecodeError:
        return json.dumps({"error": "invalid_json_arguments"}, ensure_ascii=False), []

    sources: list[dict[str, Any]] = []

    try:
        if name == "search_airport_docs":
            q = (args.get("query") or "").strip()
            if not q:
                return json.dumps({"documents": [], "error": "empty_query"}, ensure_ascii=False), []
            top_k = _parse_int(args.get("top_k"), 6, 1, 20)
            category = (args.get("category") or "").strip() or None
            relax = _parse_bool(args.get("relax_terminal"), False)
            term_arg = (args.get("terminal") or "").strip().upper() or None
            terminal = None if relax else (term_arg or default_terminal or None)
            if terminal not in (None, "T1", "T2", "CONCOURSE"):
                terminal = default_terminal

            emb = await generate_embedding(q)
            docs = await vector_repository.search_similar_documents(
                db,
                emb,
                top_k=top_k,
                category=category,
                terminal=terminal,
            )
            payload = {"documents": [_doc_public_dict(d) for d in docs]}
            sources = [
                {"doc_id": d.doc_id, "title": d.title, "source_url": d.source_url}
                for d in docs
            ]
            return json.dumps(payload, ensure_ascii=False), sources

        if name == "search_airport_docs_keyword":
            q = (args.get("query") or "").strip()
            if len(q) < 2:
                return json.dumps({"documents": [], "error": "query_too_short"}, ensure_ascii=False), []
            top_k = _parse_int(args.get("top_k"), 8, 1, 30)
            category = (args.get("category") or "").strip() or None
            term_arg = (args.get("terminal") or "").strip().upper() or None
            terminal = term_arg if term_arg in ("T1", "T2", "CONCOURSE") else default_terminal
            docs = await vector_repository.search_keyword_documents(
                db,
                q,
                top_k=top_k,
                category=category,
                terminal=terminal,
            )
            payload = {"documents": [_doc_public_dict(d) for d in docs]}
            sources = [
                {"doc_id": d.doc_id, "title": d.title, "source_url": d.source_url}
                for d in docs
            ]
            return json.dumps(payload, ensure_ascii=False), sources

        if name == "list_airport_doc_categories":
            cats = await vector_repository.list_distinct_categories(db)
            return json.dumps({"categories": cats}, ensure_ascii=False), []

        if name == "get_airport_document":
            doc_id = (args.get("doc_id") or "").strip()
            if not doc_id:
                return json.dumps({"document": None, "error": "missing_doc_id"}, ensure_ascii=False), []
            doc = await vector_repository.get_document_by_id(db, doc_id)
            if not doc:
                return json.dumps({"document": None, "found": False}, ensure_ascii=False), []
            d = _doc_public_dict(doc)
            sources = [{"doc_id": doc.doc_id, "title": doc.title, "source_url": doc.source_url}]
            return json.dumps({"document": d, "found": True}, ensure_ascii=False), sources

        if name == "search_airport_docs_hybrid":
            q = (args.get("query") or "").strip()
            if not q:
                return json.dumps({"documents": [], "error": "empty_query"}, ensure_ascii=False), []
            top_k = _parse_int(args.get("top_k"), 6, 1, 20)
            category = (args.get("category") or "").strip() or None
            term_arg = (args.get("terminal") or "").strip().upper() or None
            terminal = term_arg if term_arg in ("T1", "T2", "CONCOURSE") else default_terminal

            emb = await generate_embedding(q)
            docs = await search_hybrid_documents(
                db,
                emb,
                q,
                top_k=top_k,
                category=category,
                terminal=terminal,
            )
            payload = {"documents": [_doc_public_dict(d) for d in docs]}
            sources = [
                {"doc_id": d.doc_id, "title": d.title, "source_url": d.source_url}
                for d in docs
            ]
            return json.dumps(payload, ensure_ascii=False), sources

        return json.dumps({"error": f"unknown_tool:{name}"}, ensure_ascii=False), []
    except Exception as e:
        logger.exception("도구 실행 실패 name=%s", name)
        return json.dumps({"error": str(e)}, ensure_ascii=False), []
