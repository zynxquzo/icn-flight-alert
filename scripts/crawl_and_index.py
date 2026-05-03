#!/usr/bin/env python3
"""
인천공항 공식 사이트에서 HTML을 수집·파싱한 뒤 임베딩하여 airport_documents에 적재합니다.

사용 예:
  uv run python scripts/crawl_and_index.py --facilities --terminal T1
  uv run python scripts/crawl_and_index.py --food
  uv run python scripts/crawl_and_index.py --all

Chroma 사용 시(.env): VECTOR_BACKEND=chroma
  (RAG 문서만 로컬 Chroma에 적재, CHROMA_PERSIST_DIR 로 경로 지정 가능)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import flight_alert.models  # noqa: F401, E402 — ORM 메타데이터에 airport_documents 등 등록
from database import async_session_maker, run_alembic_upgrade  # noqa: E402
from flight_alert.repositories.vector_repository import (
    upsert_document,
    use_chroma_backend,
)  # noqa: E402
from flight_alert.services.crawler_service import (  # noqa: E402
    crawl_airport_facilities,
    crawl_airport_food,
)
from flight_alert.services.document_parser_service import (  # noqa: E402
    build_embedding_text,
    parse_facility_html,
    parse_food_html,
)
from flight_alert.services.embedding_service import generate_embedding_sync  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def ensure_schema() -> None:
    """앱을 띄우지 않고 스크립트만 실행할 때 Alembic으로 스키마를 head까지 맞춥니다."""
    run_alembic_upgrade()
    if use_chroma_backend():
        logger.info("VECTOR_BACKEND=chroma — RAG 문서는 ChromaDB에만 적재합니다.")
    else:
        logger.info("DB 스키마 확인·생성 완료 (airport_documents 포함)")


async def _index_docs(docs: list[dict], label: str) -> int:
    if not docs:
        logger.warning("%s: 파싱된 문서가 없습니다.", label)
        return 0
    n = 0
    if use_chroma_backend():
        for doc in docs:
            text = build_embedding_text(doc)
            emb = generate_embedding_sync(text)
            payload = {**doc, "embedding": emb}
            await upsert_document(None, payload)
            n += 1
        logger.info("%s: %s개 문서 인덱싱 완료 (Chroma)", label, n)
        return n

    async with async_session_maker() as db:
        try:
            for doc in docs:
                text = build_embedding_text(doc)
                emb = generate_embedding_sync(text)
                payload = {**doc, "embedding": emb}
                await upsert_document(db, payload)
                n += 1
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    logger.info("%s: %s개 문서 인덱싱 완료", label, n)
    return n


async def run_facilities(terminal: str) -> int:
    html, url = await crawl_airport_facilities(terminal)
    docs = parse_facility_html(
        html,
        source_url=url,
        default_terminal=terminal.upper(),
    )
    return await _index_docs(docs, f"편의시설({terminal})")


async def run_food() -> int:
    html, url = await crawl_airport_food()
    docs = parse_food_html(html, source_url=url)
    return await _index_docs(docs, "식음료")


async def main_async(args: argparse.Namespace) -> None:
    ensure_schema()
    total = 0
    if args.all or args.facilities:
        total += await run_facilities(args.terminal)
    if args.all or args.food:
        total += await run_food()
    if not args.all and not args.facilities and not args.food:
        logger.error("--facilities, --food, --all 중 하나를 지정하세요.")
        raise SystemExit(2)
    logger.info("총 반영 문서 수(누적 실행 기준 아님): %s", total)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="인천공항 공식 페이지 크롤링 후 벡터 인덱싱"
    )
    parser.add_argument(
        "--terminal",
        default="T1",
        help="편의시설 fnctNo 매핑에 쓰는 터미널 키 (기본 T1)",
    )
    parser.add_argument("--facilities", action="store_true", help="편의 · 공공시설")
    parser.add_argument("--food", action="store_true", help="식음료 목록")
    parser.add_argument("--all", action="store_true", help="편의시설 + 식음료")
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
