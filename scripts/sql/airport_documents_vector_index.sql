-- =============================================================================
-- airport_documents: pgvector·검색 보조 인덱스
-- =============================================================================
-- HNSW 는 pgvector 0.5.0 이상에서 지원됩니다. CREATE 시 오류가 나면
-- 아래 주석 처리된 IVFFlat 블록으로 대체하고, HNSW CREATE 줄은 제거하세요.
-- =============================================================================
-- 전제:
--   - 테이블 public.airport_documents 는 애플리케이션(SQLAlchemy) 기동 시 생성됩니다.
--   - 임베딩 차원: 1536 (OpenAI text-embedding-3-small 기본)
-- 실행:
--   psql "$DATABASE_URL" -f scripts/sql/airport_documents_vector_index.sql
--   또는 DBeaver / pgAdmin 에서 본 파일 실행
--
-- 주의:
--   - CREATE EXTENSION 은 DB 슈퍼유저 또는 확장 설치 권한이 필요할 수 있습니다.
--   - 대용량 테이블에서 인덱스만 재생성할 때는 CREATE INDEX CONCURRENTLY 를
--     단일 문장·트랜잭션 밖에서 수동으로 실행하는 것이 안전합니다.
-- =============================================================================

-- pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- 키워드 도구(search_airport_docs_keyword)의 ILIKE 성능 보조 (선택)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ---------------------------------------------------------------------------
-- B-tree: 필터 조합 (터미널 + 카테고리 동시 필터 시 플래너에 유리)
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_airport_documents_terminal_category
    ON public.airport_documents (terminal, category);

CREATE INDEX IF NOT EXISTS idx_airport_documents_category_subcategory
    ON public.airport_documents (category, subcategory);

-- ---------------------------------------------------------------------------
-- 벡터 인덱스 (권장: HNSW, 코사인 거리 <=> 와 동일 계열 vector_cosine_ops)
--   - 데이터 규모가 작아도 동작합니다.
--   - m / ef_construction 은 정확도·빌드 시간·인덱스 크기 트레이드오프입니다.
--   - 이미 다른 이름의 벡터 인덱스가 있으면 충돌·중복 검색을 피해 하나만 유지하세요.
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_airport_documents_embedding_hnsw
    ON public.airport_documents
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ---------------------------------------------------------------------------
-- IVFFlat (대량 데이터·HNSW 미지원 구버전 pgvector 시 대안)
--   - lists 는 대략 min(행수/1000, sqrt(행수)) ~ 행수/1000 사이에서 조정합니다.
--   - 행 수가 lists 보다 많아야 품질이 나옵니다. 소량이면 HNSW 만 사용하세요.
-- 아래 블록은 기본 비활성(주석). 필요 시 HNSW 와 동시 사용은 비권장(중복)이므로
-- HNSW DROP 후 주석 해제하세요.
-- ---------------------------------------------------------------------------
-- DROP INDEX IF EXISTS public.idx_airport_documents_embedding_hnsw;
-- CREATE INDEX IF NOT EXISTS idx_airport_documents_embedding_ivfflat
--     ON public.airport_documents
--     USING ivfflat (embedding vector_cosine_ops)
--     WITH (lists = 100);

-- ---------------------------------------------------------------------------
-- 제목 부분 일치(트라이그램). 본문은 길이가 커질 수 있어 제목만 인덱싱합니다.
-- 본문 ILIKE 가 느리면 content 에 별도 GIN(pg_trgm) 추가를 검토하세요.
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_airport_documents_title_trgm
    ON public.airport_documents
    USING gin (title gin_trgm_ops);

-- ---------------------------------------------------------------------------
-- 통계 갱신 (쿼리 플래너)
-- ---------------------------------------------------------------------------
ANALYZE public.airport_documents;

-- =============================================================================
-- 데이터(문서 행) 적재 — 인덱스보다 먼저 또는 나중에 실행 가능
-- =============================================================================
-- 1) 스키마 적용:  uv run alembic upgrade head  (또는 앱 기동 시 자동 적용)
-- 2) 공항 사이트 크롤·임베딩 적재:
--      uv run python scripts/crawl_and_index.py --facilities
--      uv run python scripts/crawl_and_index.py --all
-- 3) 본 SQL 실행(인덱스):  uv run python scripts/apply_airport_indexes.py
--    또는:  psql "$DATABASE_URL" -f scripts/sql/airport_documents_vector_index.sql
-- =============================================================================
