#!/usr/bin/env python3
"""
airport_documents_vector_index.sql 을 PostgreSQL에 적용합니다.

  DATABASE_URL 이 설정된 상태에서:
  uv run python scripts/apply_airport_indexes.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SQL_FILE = ROOT / "scripts" / "sql" / "airport_documents_vector_index.sql"


def main() -> None:
    try:
        import psycopg2
    except ImportError as e:
        print("psycopg2 가 필요합니다. uv sync 후 다시 실행하세요.", e)
        sys.exit(1)

    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    url = os.getenv("DATABASE_URL")
    if not url:
        print("DATABASE_URL 환경 변수가 없습니다.")
        sys.exit(1)

    sql = SQL_FILE.read_text(encoding="utf-8")
    conn = psycopg2.connect(url)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        print(f"적용 완료: {SQL_FILE}")
    except Exception as e:
        print("SQL 적용 실패:", e)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
