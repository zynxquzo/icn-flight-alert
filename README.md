# ✈️ ICN Flight Alert - 인천공항 비행편 실시간 알림 시스템

인천공항을 이용하는 여행객들의 편리한 여행을 위한 **FastAPI 기반 비행편 실시간 모니터링 및 알림 서비스**입니다.

비행편 변경 사항을 자동으로 감지하고 이메일로 알려주며, RAG 기반 AI 챗봇을 통해 공항 대기 시간 동안 유용한 정보를 제공합니다.

---

## 📚 Table of Contents

- [Tech Stack](#-tech-stack)
- [Async stack & DATABASE_URL](#async-stack--database_url)
- [Database Structure](#-database-structure)
- [Database migrations (Alembic)](#-database-migrations-alembic)
- [Key Features](#-key-features)
- [Architecture & Design Patterns](#-architecture--design-patterns)
- [Business Logic Location](#-business-logic-location)
- [API Documentation](#-api-documentation)
- [Getting Started](#️-getting-started)
- [Deployment](#-deployment)
- [RAG System Setup](#-rag-system-setup)
- [Troubleshooting](#-troubleshooting)
- [Future Roadmap](#-future-roadmap)
- [Retrospective](#-retrospective)

---

## 🛠 Tech Stack

| Category | Technology |
|----------|-----------|
| **Framework** | FastAPI — 라우트는 `async def`, DB·외부 HTTP는 비동기 호출 |
| **Database** | PostgreSQL |
| **DB 드라이버 (앱 런타임)** | **asyncpg** (`postgresql+asyncpg://`) |
| **DB 드라이버 (마이그레이션·동기 스크립트)** | **psycopg2** — Alembic, `scripts/apply_airport_indexes.py` 등 |
| **ORM** | SQLAlchemy 2.0 — `create_async_engine`, `async_sessionmaker`, `AsyncSession`, `expire_on_commit=False` |
| **Migrations** | Alembic (로컬은 앱 기동 시 `upgrade head` 기본; 프로덕션은 환경 변수로 끄고 CI/CD에서 적용 권장) |
| **Authentication** | JWT(액세스·만료 `JWT_EXPIRE_MINUTES`) + **리프레시 토큰**(불투명 문자열 SHA-256 저장·회전), bcrypt, 이메일 인증·비밀번호 재설정(SMTP 링크) |
| **External API** | 인천국제공항 공공데이터 OpenAPI — **`httpx.AsyncClient`** (비동기 HTTP) |
| **Email Service** | Gmail SMTP |
| **AI Service** | OpenAI (GPT-4o-mini, text-embedding-3-small) |
| **Vector Store** | PostgreSQL 배열 임베딩 / ChromaDB (선택) |
| **Crawling** | httpx, BeautifulSoup4, lxml |
| **Scheduler** | APScheduler `BackgroundScheduler` — 주기 작업에서 `asyncio.run`으로 비동기 갱신 로직 실행 |
| **Dependency Management** | uv |
| **Environment** | python-dotenv |

### ⚡ Async stack & DATABASE_URL

앱은 **비동기 SQLAlchemy + asyncpg** 기준으로 동작합니다. 개념적으로는 아래와 같이 맞춰 두었습니다.

| 동기(과거 패턴) | 이 저장소의 비동기 대응 |
|----------------|------------------------|
| psycopg2 / `create_engine` | **asyncpg** / `create_async_engine` |
| `sessionmaker`, `Session` | `async_sessionmaker`, **`AsyncSession`** |
| `def` 엔드포인트 | **`async def`** 엔드포인트 |
| `db.scalars(stmt)` 등 | **`await db.scalars(stmt)`** (및 `execute`·`commit`·`flush`도 동일하게 `await`) |
| 세션 기본 `expire_on_commit=True` | **`expire_on_commit=False`** (비동기 컨텍스트에서 지연 로딩 이슈 완화) |
| 지연 로딩에 의존 | 관계가 필요하면 **`selectinload` 등으로 명시적 eager load** 권장 |
| `time.sleep` / `requests` | `asyncio.sleep` / **`httpx`** (인천 OpenAPI는 `httpx.AsyncClient`) |

**`DATABASE_URL` 처리**

- `.env`에 **`postgresql://user:pass@host:5432/db`** 형태만 적어도 됩니다. 앱 기동 시 내부에서 **`postgresql+asyncpg://`** 로 바꿔 연결합니다.
- 이미 **`postgresql+asyncpg://`** 를 쓰면 그대로 사용합니다.
- **Alembic**과 **`scripts/apply_airport_indexes.py`**(psycopg2)는 동기 연결이 필요하므로, 실행 시 URL을 **`postgresql+psycopg2://`** 에 맞게 정규화합니다(`database.normalize_database_url_to_sync_psycopg2`).
- 크롤·인덱싱 스크립트 `scripts/crawl_and_index.py`는 PostgreSQL 모드에서 **`async_session_maker`** 로 비동기 세션을 열고 문서를 적재합니다.

**스케줄러**: APScheduler가 백그라운드 스레드에서 돌기 때문에, 비행편 갱신 job 안에서는 **`asyncio.run()`** 으로 한 번에 비동기 세션·서비스 로직을 실행합니다.

---

## 🏗 Database Structure

![ERD](https://github.com/user-attachments/assets/7a790f94-26af-4051-ad42-cfd4842c4414)

데이터 무결성을 위해 `User`, `Flight`, `FlightStatusLog`, `Notification` 간의 관계를 설계하였으며, JWT 인증을 통한 사용자별 비행편 관리를 지원합니다.

`User`에는 **`email_verified`**(이메일 인증 여부)가 있으며, **`refresh_tokens`**(세션 갱신용), **`user_security_tokens`**(비밀번호 재설정·이메일 인증용 일회성 토큰) 테이블이 별도로 둡니다.

RAG용 `AirportDocument` 테이블은 비행편 도메인과 독립적으로 운영되며, `VECTOR_BACKEND=postgres`(기본) 모드에서만 사용됩니다.

---

## 🗄 Database migrations (Alembic)

스키마 변경은 **코드 리비전(Alembic migration 파일)**으로 관리합니다. 프로젝트 루트에 `alembic.ini`, 마이그레이션 스크립트는 `alembic/versions/`에 둡니다.

| 작업 | 명령 |
|------|------|
| DB를 최신 스키마로 맞춤 | `uv run alembic upgrade head` |
| 모델 변경 후 새 마이그레이션 초안 생성 | `uv run alembic revision --autogenerate -m "변경 요약"` |
| 한 단계 되돌림 | `uv run alembic downgrade -1` |
| 현재 DB에 적용된 리비전 확인 | `uv run alembic current` |

**초기 baseline**(`0001_baseline`)은 ORM `Base.metadata`와 동일한 결과를 `create_all`로 한 번에 반영합니다. 이후 변경은 `--autogenerate`로 만든 리비전을 검토·수정한 뒤 커밋하는 흐름을 권장합니다.

**애플리케이션**: `main.py` lifespan에서 `run_alembic_on_app_startup()`을 호출합니다. 기본값(`RUN_ALEMBIC_ON_STARTUP` 미설정 또는 `true`)이면 기동 시 `head`까지 적용하고, **다중 인스턴스·오토스케일** 환경에서는 인스턴스가 동시에 `upgrade`를 돌리며 락·경합이 날 수 있으므로 `RUN_ALEMBIC_ON_STARTUP=false`로 끄고, **배포/릴리스 직전에** `uv run alembic upgrade head`만 실행하는 방식을 권장합니다.

**인덱싱 스크립트** `scripts/crawl_and_index.py`는 기존처럼 Alembic `upgrade head`를 그대로 호출합니다(단발 스크립트이므로 앱과 달리 동시 실행 겹침 이슈가 적음). PostgreSQL 모드에서는 **비동기 세션**으로 `airport_documents`에 적재합니다.

**Alembic과 `DATABASE_URL`**: Alembic은 동기 드라이버(psycopg2)로 마이그레이션을 실행합니다. `DATABASE_URL`이 `postgresql+asyncpg://` 이어도 `alembic/env.py`에서 **`postgresql+psycopg2://`** 로 바꿔 연결합니다.

**리비전 체인 (요약)**  
`0001_baseline` 이후 **`0002_add_chat_messages`**(no-op 스텁: 일부 DB에만 기록된 리비전 ID와 맞추기 위함) → **`0002_auth_refresh_email`**(`email_verified`, `refresh_tokens`, `user_security_tokens` 등) → **`0003_flight_ext`**(채팅 세션, flights 확장, pg_trgm) → **`0004_chat_fix`** → **`0005_fix_chat_role_varchar`** → **`0006_drop_chat_messages_user_id`**.

`0003`~`0006`은 처음부터 존재 여부(`has_table`/`get_columns`)를 확인하고 적용하도록 작성되어 있어 완전히 새 DB에서도, 이미 일부 적용된 기존 DB에서도 안전하다. `0002_auth_refresh_email`도 같은 이유로 존재 여부 체크가 추가되어 있다 — 자세한 배경은 [Troubleshooting #11](#-troubleshooting) 참고.

**Windows 참고**: `alembic.ini`는 ConfigParser가 시스템 로케일(예: cp949)로 읽을 수 있으므로, **주석은 ASCII만** 사용합니다. UTF-8 특수문자·한글 주석이 있으면 `UnicodeDecodeError`가 날 수 있습니다.

| 환경 변수 | 설명 |
|-----------|------|
| `RUN_ALEMBIC_ON_STARTUP` | `true`(기본): 앱 프로세스 기동 시 `alembic upgrade head` 실행. `false`: 건너뜀 — 이때는 배포 파이프라인 등에서 스키마를 맞춰야 함. |

---

## ✨ Key Features

### 🔐 User Authentication

* **Security**: JWT 기반 인증과 `bcrypt` 암호화 알고리즘을 사용한 안전한 회원가입 및 로그인
* **Authorization**: 본인이 등록한 비행편만 조회/수정/삭제 가능 (403 Forbidden)
* **액세스·리프레시 토큰**: 로그인 시 **`access_token`** + **`refresh_token`** 발급. `POST /auth/refresh`로 액세스 재발급 시 리프레시는 **회전**(기존 행 폐기 후 새 토큰). `POST /auth/logout` 시 액세스 JWT는 `jti` **블랙리스트**, 해당 사용자의 리프레시 토큰은 **전부 폐기**
* **액세스 JWT**: 기본 만료 `JWT_EXPIRE_MINUTES`(기본 30분). 만료·무효 시 `401` + `error.code` (`TOKEN_EXPIRED`, `TOKEN_INVALID`, `TOKEN_REVOKED`, 리프레시 실패 시 `REFRESH_INVALID` 등)
* **이메일 인증**: 가입 시 `email_verified=false` 및( SMTP 설정 시) 인증 메일 발송, `GET /auth/verify-email?token=` 로 완료. `POST /auth/resend-verification`(로그인 필요)으로 재발송
* **비밀번호 재설정**: `POST /auth/forgot-password`(응답 항상 204), `POST /auth/reset-password` 로 새 비밀번호 설정(성공 시 해당 사용자 리프레시 전부 폐기)
* **선택**: `REQUIRE_EMAIL_VERIFICATION=true` 이면 **미인증 계정은 로그인 403**
* **인증 메일·재설정 링크**: 프론트 주소는 **`FRONTEND_PUBLIC_URL`**(기본 `http://localhost:5173`)을 사용합니다.

### 📅 Advanced Flight Monitoring System

실시간 모니터링과 자동 감지 로직을 통해 사용자 편의성과 정확한 알림을 제공합니다.

* **실시간 API 연동**: 인천공항 공공데이터 OpenAPI를 **`httpx` 비동기 클라이언트**로 호출하여 실제 비행편 정보 조회
* **자동 데이터 채우기**: 비행편 등록 시 항공사, 공항, 게이트, 터미널 등 자동 입력
* **스케줄러**: APScheduler를 통해 10분마다 활성 비행편 자동 갱신(job 내부는 `asyncio.run` + 비동기 DB/API)
* **변경 감지**: 게이트 변경, 터미널 변경, 지연, 결항을 자동으로 감지
* **상태 관리**: 활성화/비활성화 상태로 모니터링 on/off 제어 가능
* **권한 검증**: 모든 비행편 API에 JWT 인증 적용 및 본인 확인 로직

### 📧 Email Notification System

* **자동 알림**: 변경 사항 감지 시 즉시 이메일 발송
* **HTML 템플릿**: 보기 좋은 HTML 이메일 형식으로 제공
* **알림 타입**: 게이트 변경, 터미널 변경, 지연, 결항 4가지 타입 지원
* **전송 이력**: 모든 알림의 전송 성공/실패 여부 기록
* **수동 감지**: `POST /notifications/flights/{flight_pk}/check` 또는 `POST /flights/{flight_pk}/refresh`로 인천공항 API를 즉시 조회·변경 감지 후 알림·메일 생성
* **수동 조회**: `GET /notifications`, `GET /notifications/flights/{flight_pk}`로 DB에 저장된 알림 이력 조회
* **Gmail SMTP**: Gmail 앱 비밀번호를 통한 안전한 이메일 발송
* **트랜잭션 메일**: 비행편 알림 외에 **이메일 인증·비밀번호 재설정** 안내에 `EmailService.send_simple_email` 사용(동일 SMTP 설정)

### 🤖 RAG-Powered AI Airport Assistant

인천공항 공식 웹사이트 정보를 기반으로 정확한 안내를 제공합니다.

* **OpenAI 연동**: GPT-4o-mini 답변, text-embedding-3-small 임베딩
* **Agentic RAG**: 도구 호출 기반 검색 (`search_airport_docs`, `search_airport_docs_keyword`, `list_airport_doc_categories`, `get_airport_document`)
* **문서 인덱싱**: 인천공항 공식 사이트 크롤링 및 파싱 후 벡터 DB 저장
* **맞춤 추천**: 대기 시간(`wait_time_hours`)과 터미널 정보를 고려한 개인화된 답변
* **유연한 벡터 저장소**: PostgreSQL 배열 또는 ChromaDB 선택 가능 (`VECTOR_BACKEND` 설정)
* **API**: `GET /chatbot` (소개), `POST /chatbot/chat` (대화) — **JWT 필수**, 응답에 `mode`, `sources` 포함

### 📊 Comprehensive Logging System

* **FlightStatusLog**: 모든 변경 사항을 시간순으로 기록
* **변경 타입**: gate_change, terminal_change, delay, cancel로 분류
* **상세 정보**: 게이트 번호, 터미널, 예정/실제 시간, 비고 등 저장
* **조회 필터**: change_type으로 특정 유형의 변경 이력만 조회 가능

### 🛡 Robust Exception Handling

* **커스텀 예외**: NotFoundException, BadRequestException, APIException
* **전역 핸들러**: 모든 예외를 중앙에서 관리하여 일관된 에러 응답 제공
* **에러 형식**: `{"success": false, "error": {"code": "...", "message": "..."}}`
* **디버깅 지원**: 상세한 에러 메시지로 문제 해결 용이

---

## 🏗 Architecture & Design Patterns

### 🔄 Layered Architecture

프로젝트는 명확한 책임 분리를 위해 계층화된 아키텍처를 사용합니다.

```
┌─────────────────────────────────────────┐
│           main.py (FastAPI)             │  ← 서버 시작점, 라우터 등록
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│         Routers (API Layer)             │  ← 요청/응답 처리
│  - auth_router.py                       │
│  - user_router.py                       │
│  - flight_router.py                     │
│  - notification_router.py               │
│  - chatbot_router.py                    │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│      Services (Business Logic)          │  ← 비즈니스 로직
│  - auth_service.py                      │
│  - flight_service.py                    │
│  - notification_service.py              │
│  - incheon_api_service.py               │
│  - email_service.py                     │
│  - chatbot_service.py                   │
│  - embedding_service.py                 │
│  - crawler_service.py                   │
│  - document_parser_service.py           │
│  - scheduler_service.py                 │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│    Repositories (Data Access)           │  ← DB / 벡터 저장소
│  - user_repository.py                   │
│  - token_repository.py                  │
│  - flight_repository.py                 │
│  - notification_repository.py           │
│  - flight_status_log_repository.py      │
│  - vector_repository.py (+ Chroma 분기) │
│  - chroma_rag_store.py (선택)           │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│      RAG Agent (OpenAI tools)           │
│  - flight_alert/rag/agent/              │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│      Models (Database Schema)           │  ← 테이블 정의
│  - user.py                              │
│  - flight.py                            │
│  - notification.py                      │
│  - flight_status_log.py                 │
│  - airport_document.py (RAG, PG 모드)   │
└─────────────────────────────────────────┘
```

### 🚀 Performance & Reliability

* **비동기 I/O**: FastAPI 이벤트 루프에서 DB(asyncpg)·인천 OpenAPI(httpx) 대기 시 스레드 풀에 맡기지 않고 논블로킹으로 처리
* **Transaction Management**: `AsyncSession` 트랜잭션(`await commit` / `rollback`)으로 데이터 무결성 보장
* **외부 API 에러 처리**: 인천공항 API 호출 실패 시에도 기본 정보로 등록 가능
* **Scheduler 안정성**: 백그라운드 스레드에서 주기 실행; 개별 비행편 갱신 실패 시에도 다음 편·다음 주기에 영향 최소화
* **이메일 재시도**: 전송 실패 시 is_sent=False로 기록하여 재시도 가능
* **라우팅 최적화**: 고정 경로를 동적 경로보다 우선 배치하여 경로 충돌 방지

---

## 🛡 Business Logic Location

### 인증 관련

| 비즈니스 로직 | 구현 위치 | 방어 방식 |
|---|---|---|
| 이메일 중복 검증 | `auth_service.signup` | 서비스 레이어 검증 (409) |
| 비밀번호 해싱 | `auth_service._hash_password` | bcrypt 단방향 암호화 |
| 토큰 만료 검증 | `auth_service.get_current_user` | JWT ExpiredSignatureError (401) |
| 토큰 서명 검증 | `auth_service.get_current_user` | JWT InvalidTokenError (401) |

### 비행편 관련

| 비즈니스 로직 | 구현 위치 | 방어 방식 |
|---|---|---|
| 본인 비행편만 접근 | `flight_router` 각 엔드포인트 | user_id 검증 (403) |
| 비행편 정보 자동 채우기 | `flight_service.create_flight` | IncheonAPIService 연동 |
| 라우트 정의 순서 | `flight_router.py` 상단 주석 | 고정 경로를 동적 경로보다 위에 배치 |
| 변경 사항 자동 감지 | `flight_service.refresh_flight` | 게이트/터미널/시간/비고 비교 |
| FlightStatusLog 자동 생성 | `flight_service.refresh_flight` | 변경 감지 시 자동 저장 |
| Notification 자동 생성 | `flight_service.refresh_flight` | 변경 감지 시 자동 저장 |
| 이메일 자동 발송 | `flight_service.refresh_flight` | EmailService 호출 |
| 사용자 정보 자동 연동 | `flight_router.create_flight` | JWT 토큰에서 user_id·user_email 추출 |

### 스케줄러 관련

| 비즈니스 로직 | 구현 위치 | 방어 방식 |
|---|---|---|
| 10분마다 자동 갱신 | `scheduler_service.start` | APScheduler BackgroundScheduler |
| 비동기 갱신 실행 | `scheduler_service.refresh_active_flights` → `_refresh_active_flights_async` | 스레드에서 `asyncio.run`, `async_session_maker` + `flight_service.refresh_flight` |
| 활성 비행편만 갱신 | `_refresh_active_flights_async` | is_active=True 필터 |
| 오늘~모레 비행편만 조회 | `_refresh_active_flights_async` | flight_date 범위 필터 |

### 알림 관련

| 비즈니스 로직 | 구현 위치 | 방어 방식 |
|---|---|---|
| 본인 알림·본인 비행편만 조회 | `notification_router` | JWT + 비행편 소유자 검증 |
| 저장된 알림 이력 수동 조회 | `notification_service.read_*_notifications` | GET `/notifications` 계열 |
| 수동 변경 감지·알림 생성 | `notification_router` + `flight_service.refresh_flight` | POST `/notifications/flights/{flight_pk}/check` (refresh와 동일 로직) |
| 알림 타입별 필터링 | `notification_service.read_user_notifications` | notification_type 필터 |
| 전송 성공/실패 기록 | `email_service.send_notification_email` | is_sent boolean 플래그 |

### RAG 챗봇 관련

| 비즈니스 로직 | 구현 위치 | 방어 방식 |
|---|---|---|
| 문서 인덱싱 | `scripts/crawl_and_index.py` | 크롤링 + 파싱 + 임베딩 저장 |
| 벡터 검색 (코사인) | `vector_repository.py` | PostgreSQL 배열(비동기 세션) 또는 Chroma |
| 키워드 검색 | `vector_repository.py` | PostgreSQL ILIKE(비동기) 또는 Chroma 메타데이터 |
| 에이전트 도구 호출 | `rag/agent/tools.py` | OpenAI function calling |
| 모드 분기 | `chatbot_service.py` | 문서 존재 여부로 agent/rag/legacy 결정 |

---

## 📖 API Documentation

![API](https://github.com/user-attachments/assets/0715b1ee-bc51-48f0-9a22-0fb02f6ad4db)

모든 API 명세는 Swagger UI를 통해 시각적으로 확인하고 테스트할 수 있습니다.

* **Docs 주소**: `http://localhost:8000/docs`
* **API 명세**: [API.md](./API.md)
* **Notion 주소** [Notion](https://www.notion.so/ICN-Flight-Alert-3434e9ce85e980d1880fe3f3c5bb28e8)


### 엔드포인트 요약

| Method | Path | JWT 필요 | 비고 |
|--------|------|:--------:|------|
| `POST` | `/auth/signup` |  | 회원가입 (`UserResponse`에 `email_verified` 포함) |
| `POST` | `/auth/login` |  | `access_token` + **`refresh_token`** 발급 |
| `POST` | `/auth/refresh` |  | 본문 `{ "refresh_token" }` → 새 액세스·리프레시(회전) |
| `POST` | `/auth/logout` | ✅ | 액세스 블랙리스트 + 해당 사용자 리프레시 전부 폐기, 응답 204 |
| `POST` | `/auth/forgot-password` |  | 비밀번호 재설정 메일(등록된 이메일만; 응답 항상 **204**) |
| `POST` | `/auth/reset-password` |  | 본문 `token`, `new_password` |
| `GET` | `/auth/verify-email` |  | 쿼리 `token` — 이메일 인증 완료 |
| `POST` | `/auth/resend-verification` | ✅ | 인증 메일 재발송 |
| `GET` | `/me` | ✅ | 내 프로필 (`email_verified` 포함) |
| `POST` | `/flights` | ✅ | 등록 시 로그인 사용자에 연동 |
| `GET` | `/flights` | ✅ | 선택 쿼리 `is_active` (boolean) |
| `GET` | `/flights/{flight_pk}` | ✅ | 본인 아니면 **403** |
| `DELETE` | `/flights/{flight_pk}` | ✅ | 본인 아니면 **403** |
| `PATCH` | `/flights/{flight_pk}/status` | ✅ | `is_active` 변경, 본인 **403** |
| `POST` | `/flights/{flight_pk}/refresh` | ✅ | 수동 갱신, 본인 **403** |
| `GET` | `/flights/{flight_pk}/logs` | ✅ | 변경 이력, `change_type` 선택 필터, 본인만 |
| `GET` | `/notifications` | ✅ | 저장된 알림 이력 수동 조회, `notification_type` 선택 필터 |
| `GET` | `/notifications/flights/{flight_pk}` | ✅ | 해당 비행편 알림 이력 수동 조회, 본인만 |
| `POST` | `/notifications/flights/{flight_pk}/check` | ✅ | 알림 수동 감지(인천 API·변경 시 알림·메일), 본인만, 응답은 refresh와 동일 |
| `GET` | `/chatbot` | ✅ | 소개·환경 변수 안내 |
| `POST` | `/chatbot/chat` | ✅ | 챗봇; 응답 `mode`, `sources` 포함 |

프론트엔드·모바일 클라이언트는 보호된 경로에 `Authorization: Bearer <access_token>` 헤더를 포함해야 합니다. 액세스 만료 시 **`POST /auth/refresh`**로 갱신한 뒤 재시도하는 방식을 권장합니다(별도 저장소 프론트엔드 README 참고).

### 프론트엔드 연동 (CORS)

`main.py`의 `CORSMiddleware`에서 **`http://localhost:5173`**, **`http://127.0.0.1:5173`** 을 허용합니다. 

별도 저장소(예: Vite + React 기반 `icn-flight-alert-frontend`)를 로컬에서 띄울 때 동일 설정을 유지하세요.

---

## ⚙️ Getting Started

```bash
# 1. 저장소 클론
git clone https://github.com/your-repo/icn_flight_alert.git
cd icn_flight_alert

# 2. 가상환경 설정 및 패키지 설치 (uv 사용 시)
uv sync

# 3. 환경 변수 설정
cp .env.example .env
# .env 파일을 열어 아래 값을 설정하세요.

# 4. PostgreSQL 데이터베이스 생성
createdb flight_alert

# 5. DB 스키마 적용 (RUN_ALEMBIC_ON_STARTUP=true이면 서버 기동 시에도 적용됨)
uv run alembic upgrade head

# 6. (선택) RAG 문서 인덱싱 — 챗봇에 공항 공식 정보 반영
uv run python scripts/crawl_and_index.py --facilities
# 또는: uv run python scripts/crawl_and_index.py --all

# 7. (선택) PostgreSQL에 검색 보조 인덱스
# scripts/sql/airport_documents_vector_index.sql
# 또는: uv run python scripts/apply_airport_indexes.py

# 8. 서버 실행
uv run fastapi dev main.py
```

### 테스트 (pytest)

```bash
uv sync --group dev
uv run pytest -q
```

`tests/` 에서 비행편 갱신·지연 알림 조건, JWT 블랙리스트·리프레시 회전, 인천 API 응답 파싱을 검증합니다. CI는 `.github/workflows/test.yml` 을 참고하세요.

### 환경 변수 설정 예시 (`.env`)

```ini
# Database
# 앱은 asyncpg로 연결합니다. postgresql:// 만 적어도 내부에서 postgresql+asyncpg:// 로 변환됩니다.
# Alembic·psycopg2 스크립트는 동기 URL(postgresql+psycopg2)로 자동 정규화됩니다.
DATABASE_URL=postgresql://user:password@localhost:5432/flight_alert

# 앱 기동 시 Alembic 자동 적용 (로컬 true 권장; 프로덕션 다중 워커는 false + 배포 시 upgrade)
# RUN_ALEMBIC_ON_STARTUP=true

# JWT
JWT_SECRET_KEY=your-secret-key-here  # openssl rand -hex 32
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=30
# JWT_REFRESH_EXPIRE_DAYS=14

# 인증 메일·재설정 링크에 쓰는 프론트 베이스 URL (trailing slash 없이)
# FRONTEND_PUBLIC_URL=http://localhost:5173

# 가입 후 이메일 인증 없이는 로그인 불가 (기본: 미설정·false)
# REQUIRE_EMAIL_VERIFICATION=true

# 인증·재설정 토큰 유효 시간 (선택, 기본은 코드 내 상수)
# EMAIL_VERIFY_TOKEN_EXPIRE_HOURS=24
# PASSWORD_RESET_TOKEN_EXPIRE_HOURS=1

# Incheon Airport API
INCHEON_AIRPORT_API_KEY=your-api-key-here

# 추정 시각(지연) 이메일 알림 튜닝 (선택; flight_service.refresh_flight)
# 추정시각이 바뀌어도 스케줄만 살짝 고친 경우 메일을 줄이려면 아래를 조합해 사용
# FLIGHT_DELAY_MIN_DIFF_MINUTES=0   # 이전·이후 시각 차이(분)가 이 값 미만이면 메일 생략. 0 또는 미설정=변경만 있어도 알림
# FLIGHT_DELAY_REMARK_HINTS=       # 콤마 구분 부분 문자열(예: 지연,delay). 비어 있지 않으면 remark에 하나도 없으면 메일 생략

# Gmail SMTP
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password  # Gmail 앱 비밀번호
SMTP_FROM_EMAIL=your-email@gmail.com

# OpenAI
OPENAI_API_KEY=sk-proj-...

# RAG / 챗봇 (선택)
RAG_ENABLED=true
RAG_AGENT_ENABLED=true
RAG_TOP_K=5
RAG_AGENT_MODEL=gpt-4o-mini
RAG_AGENT_MAX_ROUNDS=5

# 벡터 백엔드: postgres(기본) | chroma
VECTOR_BACKEND=postgres
# CHROMA_PERSIST_DIR=.chroma_airport
# CHROMA_COLLECTION=airport_documents
```

---

## 🚀 Deployment

FastAPI(backend) + PostgreSQL + Redis + Vite/React(frontend, nginx로 서빙) 4개 컨테이너를 `docker-compose.yml` 하나로 묶어 컨테이너화했습니다. 프론트엔드 저장소(`icn-flight-alert-frontend`)가 이 저장소와 **형제 폴더**로 있어야 `docker compose`가 빌드할 수 있습니다.

```bash
cp .env.example .env   # 값 채우기
docker compose up --build -d
docker compose ps
```

| 서비스 | 역할 | 기본 포트 |
|---|---|---|
| `backend` | FastAPI (uv 기반 멀티스테이지 빌드) | 8000 |
| `frontend` | Vite 빌드 → nginx 서빙 | 8080 |
| `db` | PostgreSQL 16 | (내부용) |
| `redis` | JWT 블랙리스트 · 스케줄러 리더 락 | (내부용) |

배포는 아래 순서로 단계별로 진행했습니다.

1. **로컬 컨테이너 검증** — Docker를 처음 다루는 사람 기준으로 설치부터 `docker compose up`까지 단계별로 진행 ✅
2. **VPS 수동 배포** — Google Cloud Compute Engine의 `e2-micro` Always Free 인스턴스에, 도메인 없이 서버 공인 IP로 접속하는 구성으로 배포. VM 생성, 방화벽(VPC) 설정, SSH 접속, Docker 설치, 소스 배포, 예산 알림(Budget Alert) 설정까지 진행 ✅
3. **기본 모니터링·알람** — AWS CloudWatch 대신 Google Cloud Monitoring으로, Ops Agent 설치(메모리·디스크 지표), 이메일 알림 채널, Uptime Check(헬스체크 다운 감지), CPU 80%·디스크 85% 임계치 알림 정책까지 구성. 부하 테스트로 알림 수신까지 확인 완료 ✅
4. **도메인 연결 + HTTPS** — 가비아에서 `icnflightalert.site` 도메인 구입 후, nginx 리버스 프록시 + Let's Encrypt(Certbot)로 `https://` 접속 구성 (서브도메인 분리: 프론트=루트 도메인, 백엔드=`api.` 서브도메인) ✅

> ℹ️ 각 단계의 상세 절차는 로컬 참고용 가이드 문서로 별도 정리했으며 `.gitignore`에 등록되어 저장소에는 포함하지 않습니다. AWS는 사용하지 않는 방향으로 진행했고(비용·러닝커브 이유), Oracle Cloud는 가입 단계에서 반복적으로 실패해 Google Cloud로 전환했습니다.

**서비스 주소**: [https://icnflightalert.site](https://icnflightalert.site) (프론트엔드) / `https://api.icnflightalert.site` (백엔드 API, `/docs`에서 API 문서 확인 가능)

HTTPS까지 적용되어 있으며, GCP Cloud Monitoring으로 CPU·디스크·서비스 다운 알림은 이메일로 수신되도록 구성되어 있습니다.

---

## 🔍 RAG System Setup

### 문서 인덱싱

인천공항 공식 웹사이트 정보를 크롤링하고 벡터 DB에 저장합니다.

```bash
# 편의시설 정보만 인덱싱
uv run python scripts/crawl_and_index.py --facilities

# 모든 정보 인덱싱
uv run python scripts/crawl_and_index.py --all
```

### RAG 동작 확인

1. 위 인덱싱 스크립트를 한 번 이상 실행해 문서를 적재합니다.
2. 서버 기동 후 `http://localhost:8000/docs`에서 로그인(`POST /auth/login`)으로 토큰을 받고, **Authorize**에 `Bearer` 토큰을 입력합니다.
3. `POST /chatbot/chat` 호출 — 요청 본문 예: `{ "message": "1터미널 환전 어디 있어?", "terminal": "T1" }`
4. 응답의 `mode`가 `agent` 또는 `rag`이고 `sources`에 문서 정보가 있으면 성공

### 벡터 저장소 선택

**PostgreSQL (기본)**
- `.env`에 `VECTOR_BACKEND=postgres` 설정
- `airport_documents` 테이블에 임베딩 배열 저장
- pgvector 확장 불필요 (애플리케이션 레벨 코사인 검색)

**ChromaDB (선택)**
- `.env`에 `VECTOR_BACKEND=chroma` 설정
- 로컬 디렉토리(`.chroma_airport`)에 영속 저장
- 동일한 RAG API 사용

---

## 🚨 Troubleshooting

### 1. Flight 모델에 user_id 컬럼 추가 후 기존 데이터 문제

* **문제**: `user_id` 컬럼을 NOT NULL로 추가했는데 기존 flights 테이블에 데이터가 있어서 마이그레이션 실패
* **해결**: `DROP TABLE IF EXISTS flights CASCADE;` 실행 후 서버 재시작하여 테이블 재생성

### 2. FlightCreate 스키마에서 user_email 제거 후 호환성 문제

* **문제**: 기존 API 테스트에 `user_email` 필드가 포함되어 `422 Validation Error` 발생
* **해결**: FlightCreate 스키마에서 `user_email` 제거하고, 로그인한 사용자의 정보를 서비스 레이어에서 자동 설정

### 3. 본인 확인 로직에서 반복되는 코드

* **문제**: 여러 엔드포인트에서 동일한 본인 확인 로직 반복
* **해결**: 각 엔드포인트에서 `flight_service.read_flight_by_id()` 조회 후 `flight.user_id != current_user.user_id` 체크

### 4. 비행편 등록 시 인천공항 API 호출 실패 대응

* **설계 결정**: API 호출 실패 시에도 기본 정보로 비행편 등록 허용하여 사용자 경험 개선
* **구현**: `flight_service.create_flight()`에서 API 실패 시 기본 정보만 저장

### 5. 챗봇 정보 API 경로 혼선

* **문제**: 클라이언트가 `GET /chatbot/`만 호출하여 404 발생
* **해결**: 서비스 소개는 `GET /chatbot` (슬래시 없음) 사용

### 6. RAG가 동작하지 않고 항상 `mode: legacy`

* **원인**: `airport_documents`에 행이 없거나 `RAG_ENABLED=false`
* **해결**: `uv run python scripts/crawl_and_index.py --facilities` 또는 `--all`로 인덱싱

### 7. 크롤 스크립트에서 `airport_documents` 테이블 없음

* **해결**: 스크립트 시작 시 Alembic `upgrade head`로 스키마를 맞춥니다. `DATABASE_URL`을 설정한 뒤 `uv run alembic upgrade head`를 한 번 실행하거나, 인덱싱 스크립트를 그대로 실행하세요.

### 8. Windows에서 Chroma 사용 시

* **Chroma**: `VECTOR_BACKEND=chroma`일 때 `CHROMA_PERSIST_DIR`로 저장 경로 지정 가능
* **기본 경로**: 프로젝트 루트 `.chroma_airport` (`.gitignore`에 등록됨)

### 9. `asyncpg` / `DATABASE_URL` 연결 오류

* **증상**: 앱 기동 시 `asyncpg` 관련 연결 실패, 또는 드라이버를 찾을 수 없음
* **확인**: `uv sync`로 **`asyncpg`** 설치 여부 확인. `DATABASE_URL` 호스트·포트·DB명·비밀번호가 PostgreSQL과 일치하는지 확인
* **참고**: Alembic만 쓸 때는 psycopg2 경로이므로, 앱과 동일한 **`postgresql://...`** 호스트만 맞으면 됩니다. `postgresql+asyncpg://`를 직접 써도 앱은 그대로 사용합니다.

### 10. Alembic `Can't locate revision …` 또는 Windows에서 `alembic.ini` UnicodeDecodeError

* **원인**: DB의 `alembic_version`과 저장소의 리비전 파일이 어긋나 있거나, `alembic.ini`에 UTF-8 전용 문자(예: em dash, 한글)가 있어 Windows 로케일(cp949)로 읽을 때 실패
* **해결**: `uv run alembic current` 로 DB 버전 확인 후 `upgrade head` 또는 운영 정책에 맞게 `stamp` 조정. `alembic.ini` 주석은 ASCII만 유지

### 11. Docker로 완전히 새 DB에 배포 시 backend가 무한 재시작 (`DuplicateColumn` / `DuplicateTable`)

* **문제**: `docker compose up`으로 처음부터 새 PostgreSQL 볼륨에 마이그레이션을 돌리면 backend 컨테이너가 계속 재시작(`Restarting`)했다. `docker compose logs backend`에는 에러가 안 보이는데, 매번 `0001_baseline`부터 마이그레이션을 다시 실행하는 로그만 반복됐다.
* **원인**: `0001_baseline`이 **현재 ORM 모델 전체**로 스키마를 만드는데(`Base.metadata.create_all`), 그 안에 이미 `users.email_verified`, `refresh_tokens`, `user_security_tokens`, `chat_messages` 등이 포함되어 있다. 그런데 이후 실행되는 `0002_auth_refresh_email`과 `0004_chat_fix`는 이걸 모르고 무조건 컬럼·테이블을 다시 만들거나(`email_verified` 컬럼, `refresh_tokens`/`user_security_tokens` 테이블) 이미 없는 컬럼(`chat_messages.user_id`)을 전제로 쿼리를 실행해서 `DuplicateColumn`/`DuplicateTable` 오류로 실패했다. Alembic이 트랜잭션DDL이라 실패 시 롤백되고, `RUN_ALEMBIC_ON_STARTUP=true`라 다음 재시작에서 처음부터 똑같이 실패를 반복한 것. (기존에 `0001_baseline`이 생기기 전부터 이미 운영되던 DB에서는 0002/0004가 먼저 적용된 상태라 이 문제가 드러나지 않았음.)
* **디버깅 팁**: `docker compose logs`에 에러가 안 보이면, `docker compose run --rm --no-deps backend python -c "from database import run_alembic_upgrade; run_alembic_upgrade()"` 로 재시작 없이 직접 실행해서 traceback을 확인한다.
* **해결**: `0002_auth_refresh_email_verify.py`, `0004_chat_fix.py`에 `inspector.has_table(...)` / `get_columns(...)` 존재 여부 체크를 추가해, 컬럼·테이블이 이미 있으면 건너뛰도록 멱등하게 수정.

---

## 🚀 Future Roadmap

* [x] **JWT Authentication**: 사용자 인증 및 본인 확인 체계 구축
* [x] **Incheon Airport API**: 실시간 비행편 정보 조회
* [x] **Auto Change Detection**: 게이트, 터미널, 지연, 결항 자동 감지
* [x] **Email Notification**: Gmail SMTP를 통한 이메일 알림
* [x] **APScheduler**: 10분 주기 자동 갱신
* [x] **AI Chatbot**: OpenAI 기반 공항 안내 챗봇
* [x] **RAG / Agentic Chatbot**: 공항 공식 정보 크롤·임베딩·도구 호출 기반 챗봇
* [x] **Exception Handling**: 커스텀 예외 및 전역 핸들러
* [x] **Frontend (별도 저장소)**: Vite + React 클라이언트 연동
* [x] **Refresh JWT & 이메일 인증·비밀번호 재설정**: 리프레시 토큰 회전, SMTP 링크, 선택적 `REQUIRE_EMAIL_VERIFICATION`
* [ ] **Push Notification**: Firebase Cloud Messaging 연동
* [x] **Alembic Migration**: DB 스키마 버전 관리 및 기동 시 `upgrade head` 선택 적용(`RUN_ALEMBIC_ON_STARTUP`)
* [ ] **SMS Notification**: Twilio를 통한 문자 알림
* [ ] **Deployment**: Render / Railway / Fly.io 배포
* [x] **Test Automation**: Pytest 유닛 테스트 (`tests/` — `flight_service`, `auth_service`, `incheon_api_service`)

---

## 📝 Retrospective

인천공항 공공데이터 OpenAPI를 활용하여 **실시간 비행편 모니터링 시스템**을 구축하는 과정에서 **외부 API 연동**, **스케줄러 구현**, **이메일 알림 시스템** 등 실무에서 자주 사용되는 기술들을 경험할 수 있었습니다.

특히 FastAPI의 **의존성 주입(Dependency Injection)**을 활용한 인증 시스템 구현과 **계층화된 아키텍처(Layered Architecture)** 설계를 통해 유지보수가 용이한 백엔드 시스템의 필요성을 체감했습니다.

**APScheduler**를 통한 주기적인 백그라운드 작업 처리와 **트랜잭션 관리**를 통한 데이터 무결성 보장의 중요성을 깊이 이해하게 되었으며, 인천공항 API의 응답 형식을 파싱하고 변경 사항을 감지하여 자동으로 알림을 생성하는 로직을 구현하며 **복잡한 비즈니스 로직을 체계적으로 설계**하는 능력을 기를 수 있었습니다.

마지막으로 OpenAI GPT-4o-mini와 **RAG·에이전틱 도구 호출**을 결합해 인덱싱된 공항 정보를 근거로 답변하도록 확장하였으며, PostgreSQL 또는 **ChromaDB**로 벡터 저장소를 선택할 수 있게 하여 로컬 개발·배포 환경에 맞게 조정할 수 있도록 설계했습니다.

---

## 🔗 관련 저장소

* **Frontend**: [icn-flight-alert-frontend](https://github.com/zynxquzo/icn-flight-alert-frontend)

---

## 👨‍💻 Author

- GitHub: [@zynxquzo](https://github.com/zynxquzo)