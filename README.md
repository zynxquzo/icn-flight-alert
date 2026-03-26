# ✈️ ICN Flight Alert - 인천공항 비행편 실시간 알림 시스템

인천공항을 이용하는 여행객들의 편리한 여행을 위해 설계된 **FastAPI 기반의 비행편 실시간 모니터링 및 알림 서비스**입니다. 비행편 변경 사항을 자동으로 감지하고 이메일로 알려주며, AI 챗봇을 통해 공항 대기 시간 동안 유용한 정보를 제공합니다.

### 최근 업데이트 요약

* **Flight Router**: 모든 비행편 API에 `get_current_user` 적용(로그인 필수). 등록 시 `user_id`·`user_email`은 토큰의 사용자로 자동 연동. 상세/삭제/상태 변경/수동 갱신은 `flight.user_id`와 비교해 본인만 허용, 타인 접근 시 **403 Forbidden**. `GET /flights`는 쿼리 `is_active`로 활성·비활성 필터 가능. **고정 경로**(`POST ""`, `GET ""`)를 **동적 경로**(`/{flight_pk}` …)보다 위에 두어 라우팅 오동작을 방지.
* **Chatbot Router**: 서비스 소개 엔드포인트를 **`GET /chatbot`**(URL 끝 슬래시 없음)으로 통일. 대화는 **`POST /chatbot/chat`** (JWT 불필요).
* **CORS**: Vite 기본 개발 서버(`http://localhost:5173`, `http://127.0.0.1:5173`) 및 `Authorization` 헤더 허용으로 별도 프론트엔드 저장소와 연동 가능.

---

## 🛠 Tech Stack

* **Framework**: `FastAPI` (Asynchronous API Support)
* **Database**: `PostgreSQL`
* **ORM**: `SQLAlchemy 2.0`
* **Authentication**: `JWT (JSON Web Token)`, `bcrypt`
* **External API**: 인천국제공항 공공데이터 OpenAPI
* **Email Service**: `Gmail SMTP`
* **AI Service**: `OpenAI GPT-4o-mini`
* **Scheduler**: `APScheduler` (10분 주기 자동 갱신)
* **Dependency Management**: `uv`
* **Environment**: `python-dotenv`

---

## 🏗 Database Structure (ERD)

데이터 무결성을 위해 `User`, `Flight`, `FlightStatusLog`, `Notification` 간의 관계를 설계하였으며, JWT 인증을 통한 사용자별 비행편 관리를 지원합니다.

![ERD](https://github.com/user-attachments/assets/2b533b1a-9c20-4ffc-9b8b-e2f316af8ec7)

---

## ✨ Key Features

### 🔐 User Authentication

* **Security**: JWT 기반 인증과 `bcrypt` 암호화 알고리즘을 사용한 안전한 회원가입 및 로그인
* **Authorization**: 본인이 등록한 비행편만 조회/수정/삭제 가능 (403 Forbidden)
* **Token Management**: 30분 만료 시간이 적용된 JWT 토큰 발급

### 📅 Advanced Flight Monitoring System

사용자 편의와 정확한 알림을 위해 **실시간 모니터링**과 **자동 감지** 로직을 적용했습니다.

* **실시간 API 연동**: 인천공항 공공데이터 OpenAPI를 통한 실제 비행편 정보 조회
* **자동 데이터 채우기**: 비행편 등록 시 항공사, 공항, 게이트, 터미널 등 자동 입력
* **스케줄러**: APScheduler를 통해 10분마다 활성 비행편 자동 갱신
* **변경 감지**: 게이트 변경, 터미널 변경, 지연, 결항을 자동으로 감지
* **상태 관리**: 활성화/비활성화 상태로 모니터링 on/off 제어 가능

### 📧 Email Notification System

* **자동 알림**: 변경 사항 감지 시 즉시 이메일 발송
* **HTML 템플릿**: 보기 좋은 HTML 이메일 형식으로 제공
* **알림 타입**: 게이트 변경, 터미널 변경, 지연, 결항 4가지 타입 지원
* **전송 이력**: 모든 알림의 전송 성공/실패 여부 기록
* **Gmail SMTP**: Gmail 앱 비밀번호를 통한 안전한 이메일 발송

### 🤖 AI-Powered Airport Assistant

* **OpenAI 연동**: GPT-4o-mini 모델을 활용한 자연스러운 대화
* **맞춤 추천**: 대기 시간과 터미널 정보를 고려한 개인화된 추천
* **공항 안내**: 식사, 쇼핑, 휴식 공간, 편의시설 정보 제공
* **시간별 조언**: 3시간+, 1시간+, 1시간 미만에 따른 차별화된 안내
* **API 경로**: `GET /chatbot`으로 서비스 소개 JSON 조회, `POST /chatbot/chat`에 `{ "message", "terminal", "wait_time_hours?" }` 전송 (인증 없음)

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
│  - scheduler_service.py                 │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│    Repositories (Data Access)           │  ← DB 접근
│  - user_repository.py                   │
│  - flight_repository.py                 │
│  - notification_repository.py           │
│  - flight_status_log_repository.py      │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│      Models (Database Schema)           │  ← 테이블 정의
│  - user.py                              │
│  - flight.py                            │
│  - notification.py                      │
│  - flight_status_log.py                 │
└─────────────────────────────────────────┘
```

### 🚀 Performance & Reliability

* **Transaction Management**: SQLAlchemy의 트랜잭션을 활용한 데이터 무결성 보장
* **외부 API 에러 처리**: 인천공항 API 호출 실패 시에도 기본 정보로 등록 가능
* **Scheduler 안정성**: 에러 발생 시에도 다음 주기에 정상 작동
* **이메일 재시도**: 전송 실패 시 is_sent=False로 기록하여 재시도 가능

---

## 🛡 Business Logic & Location

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
| 라우트 정의 순서 | `flight_router.py` 상단 주석 | `POST/GET ""` 고정 경로를 `/{flight_pk}` 동적 경로보다 위에 배치 |
| 변경 사항 자동 감지 | `flight_service.refresh_flight` | 게이트/터미널/시간/비고 비교 |
| FlightStatusLog 자동 생성 | `flight_service.refresh_flight` | 변경 감지 시 자동 저장 |
| Notification 자동 생성 | `flight_service.refresh_flight` | 변경 감지 시 자동 저장 |
| 이메일 자동 발송 | `flight_service.refresh_flight` | EmailService 호출 |

### 스케줄러 관련

| 비즈니스 로직 | 구현 위치 | 방어 방식 |
|---|---|---|
| 10분마다 자동 갱신 | `scheduler_service.start` | APScheduler BackgroundScheduler |
| 활성 비행편만 갱신 | `scheduler_service.refresh_active_flights` | is_active=True 필터 |
| 오늘~모레 비행편만 조회 | `scheduler_service.refresh_active_flights` | flight_date 범위 필터 |

### 알림 관련

| 비즈니스 로직 | 구현 위치 | 방어 방식 |
|---|---|---|
| 알림 타입별 필터링 | `notification_service.read_notifications` | notification_type 필터 |
| 전송 성공/실패 기록 | `email_service.send_notification_email` | is_sent boolean 플래그 |

---

## 📖 API Documentation

모든 API 명세는 Swagger UI를 통해 시각적으로 확인하고 테스트할 수 있습니다.

* **Docs 주소**: `http://localhost:8000/docs`
* **간단 명세**: [API.md](./API.md)

![API](https://github.com/user-attachments/assets/518b856d-0f56-4b29-aae3-2cfecce1f78b)

### 엔드포인트 요약 (인증·권한)

| Method | Path | JWT 필요 | 비고 |
|--------|------|:--------:|------|
| `POST` | `/auth/signup` |  | 회원가입 |
| `POST` | `/auth/login` |  | `access_token` 발급 |
| `GET` | `/me` | ✅ | 내 프로필 |
| `POST` | `/flights` | ✅ | 등록 시 로그인 사용자에 연동 |
| `GET` | `/flights` | ✅ | 선택 쿼리 `is_active` (boolean) |
| `GET` | `/flights/{flight_pk}` | ✅ | 본인 아니면 **403** |
| `DELETE` | `/flights/{flight_pk}` | ✅ | 본인 아니면 **403** |
| `PATCH` | `/flights/{flight_pk}/status` | ✅ | `is_active` 변경, 본인 **403** |
| `POST` | `/flights/{flight_pk}/refresh` | ✅ | 수동 갱신, 본인 **403** |
| `GET` | `/flights/{flight_pk}/logs` |  | 변경 이력, `change_type` 선택 필터 |
| `GET` | `/notifications` |  | `user_email` 쿼리 필수 |
| `GET` | `/notifications/flights/{flight_pk}` |  | 해당 비행편 알림 목록 |
| `GET` | `/chatbot` |  | 소개 정보 (끝 `/` 없음) |
| `POST` | `/chatbot/chat` |  | 챗봇 대화 |

프론트엔드·모바일 클라이언트는 보호된 경로에 `Authorization: Bearer <access_token>` 헤더를 붙이면 됩니다.

### 프론트엔드 연동 (CORS)

`main.py`의 `CORSMiddleware`에서 **`http://localhost:5173`**, **`http://127.0.0.1:5173`** 을 허용합니다. 별도 저장소(예: Vite + React 기반 `icn-flight-alert-frontend`)를 로컬에서 띄울 때 동일 설정을 유지하세요. 운영 도메인을 쓰는 경우 `origins` 리스트에 URL을 추가해야 합니다.

---

## 🚨 Troubleshooting

### 1. Flight 모델에 user_id 컬럼 추가 후 기존 데이터 문제

* **문제**: `user_id` 컬럼을 NOT NULL로 추가했는데 기존 flights 테이블에 데이터가 있어서 마이그레이션 실패
* **해결**: VSCode PostgreSQL 익스텐션에서 flights 테이블 우클릭 → "Drop Table" 또는 SQL로 `DROP TABLE IF EXISTS flights CASCADE;` 실행 후 서버 재시작하여 테이블 재생성

### 2. FlightCreate 스키마에서 user_email 제거 후 호환성 문제

* **문제**: 기존 API 테스트 코드나 Postman 요청에 `user_email` 필드가 포함되어 있어 `422 Validation Error` 발생
* **해결**: FlightCreate 스키마에서 `user_email` 제거하고, 로그인한 사용자의 `current_user.email`과 `current_user.user_id`를 서비스 레이어에서 자동으로 설정하도록 변경

### 3. 본인 확인 로직에서 반복되는 코드

* **문제**: `GET /flights/{id}`, `DELETE /flights/{id}`, `PATCH /flights/{id}/status` 등 여러 엔드포인트에서 동일한 본인 확인 로직 반복
* **해결**: 각 엔드포인트에서 `flight_service.read_flight_by_id()`로 비행편 조회 후 `flight.user_id != current_user.user_id` 체크하여 403 Forbidden 반환

### 4. 비행편 등록 시 인천공항 API 호출 실패 대응

* **설계 결정**: 인천공항 API 호출이 실패하더라도 사용자가 입력한 기본 정보(flight_id, flight_date, flight_type)로 비행편 등록을 허용하여 사용자 경험 개선
* **구현 위치**: `flight_alert/services/flight_service.py`의 `create_flight()` 메서드
  ```python
  # API 호출 실패 시 기본 정보만 저장
  if not api_data:
      logger.warning(f"API 호출 실패 - 기본 정보만 저장: {flight_data.flight_id}")
      flight = Flight(
          user_id=user_id,
          user_email=user_email,
          flight_id=flight_data.flight_id,
          flight_date=flight_data.flight_date,
          flight_type=flight_data.flight_type.value,
          is_active=True,
      )
  ```
* **로그 확인**: `logger.warning(f"API 호출 실패 - 기본 정보만 저장: {flight_data.flight_id}")` 로그로 API 실패 여부 확인 가능

### 5. 챗봇 정보 API 경로(슬래시) 혼선

* **문제**: 클라이언트가 `GET /chatbot/`만 호출하거나, 반대로 서버만 끝 슬래시 경로를 열어둔 경우 404 또는 리다이렉트가 발생할 수 있음
* **해결**: 서비스 소개는 **`GET /chatbot`**(슬래시 없음)을 사용. `flight_alert/routers/chatbot_router.py`에서 루트 경로는 `@router.get("")`로 정의되어 `/chatbot`에 매핑됨

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

# 5. 서버 실행
uv run fastapi dev main.py
```

### 환경 변수 설정 예시 (`.env`)

```ini
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/flight_alert

# JWT
JWT_SECRET_KEY=your-secret-key-here  # openssl rand -hex 32
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=30

# Incheon Airport API
INCHEON_AIRPORT_API_KEY=your-api-key-here

# Gmail SMTP
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password  # Gmail 앱 비밀번호
SMTP_FROM_EMAIL=your-email@gmail.com

# OpenAI
OPENAI_API_KEY=sk-proj-...
```

---

## 🚀 Future Roadmap

* [x] **JWT Authentication**: 사용자 인증 및 본인 확인 체계 구축
* [x] **Incheon Airport API**: 실시간 비행편 정보 조회
* [x] **Auto Change Detection**: 게이트, 터미널, 지연, 결항 자동 감지
* [x] **Email Notification**: Gmail SMTP를 통한 이메일 알림
* [x] **APScheduler**: 10분 주기 자동 갱신
* [x] **AI Chatbot**: OpenAI 기반 공항 안내 챗봇
* [x] **Exception Handling**: 커스텀 예외 및 전역 핸들러
* [x] **Frontend (별도 저장소)**: Vite + React 클라이언트와 CORS·JWT 연동 가능 (`icn-flight-alert-frontend` 등)
* [ ] **Frontend 단일 모노레포**: 본 저장소에 UI 포함
* [ ] **React Native** 등 모바일 네이티브 앱
* [ ] **Push Notification**: Firebase Cloud Messaging 연동
* [ ] **SMS Notification**: Twilio를 통한 문자 알림
* [ ] **RAG Chatbot**: 인천공항 실제 정보 기반 고도화된 챗봇
* [ ] **Deployment**: Render / Railway / Fly.io 배포
* [ ] **Test Automation**: Pytest를 이용한 유닛 테스트

---

## 📝 Retrospective

인천공항 공공데이터 OpenAPI를 활용하여 **실시간 비행편 모니터링 시스템**을 구축하는 과정에서 **외부 API 연동**, **스케줄러 구현**, **이메일 알림 시스템** 등 실무에서 자주 사용되는 기술들을 경험할 수 있었습니다. 특히 FastAPI의 **의존성 주입(Dependency Injection)** 을 활용한 인증 시스템 구현과 **계층화된 아키텍처(Layered Architecture)** 설계를 통해 유지보수가 용이한 백엔드 시스템의 필요성을 체감했습니다. 

또한 **APScheduler**를 통한 주기적인 백그라운드 작업 처리와 **트랜잭션 관리**를 통한 데이터 무결성 보장의 중요성을 깊이 이해하게 되었습니다. 인천공항 API의 응답 형식을 파싱하고, 변경 사항을 감지하여 자동으로 알림을 생성하는 로직을 구현하며 **복잡한 비즈니스 로직을 체계적으로 설계**하는 능력을 기를 수 있었습니다.

마지막으로 OpenAI GPT-4o-mini를 활용한 **AI 챗봇 통합**을 통해 단순한 CRUD API를 넘어 **AI 기술을 실제 서비스에 접목**하는 경험을 쌓을 수 있었고, 향후 RAG(Retrieval-Augmented Generation) 기반 챗봇으로 고도화하여 더욱 정확한 공항 정보를 제공하는 방향으로 발전시킬 계획입니다.

---

## 👨‍💻 Author

- GitHub: [@zynxquzo](https://github.com/zynxquzo)
- Email: prettymysky@gmail.com