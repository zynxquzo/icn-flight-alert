# API

FastAPI 앱은 `main.py`에서 구동되며, 기본 OpenAPI 문서는 `/docs`, `/redoc` 입니다.  
DB는 PostgreSQL(`DATABASE_URL`), ORM 모델은 `flight_alert/models/` 와 동일한 테이블 이름을 사용합니다.

## 인증

대부분의 비행·사용자 API는 `Authorization: Bearer <JWT>` 헤더가 필요합니다.  
예외: `/`, `/health`, `/auth/*`, `GET /flights/{flight_pk}/logs`, `GET /notifications/*`, `GET|POST /chatbot/*`.

---

## 엔드포인트 요약

| URL | Method | 인증 | 설명 |
|-----|--------|------|------|
| `/` | GET | 불필요 | 헬스 체크 (상태·docs 안내) |
| `/health` | GET | 불필요 | 헬스 체크 (간단) |
| `/auth/signup` | POST | 불필요 | 회원가입 (`UserCreate`: email, password) → `UserResponse` |
| `/auth/login` | POST | 불필요 | 로그인 (`UserLogin`) → `TokenResponse` (`access_token`, `token_type`) |
| `/me` | GET | 필요 | 현재 사용자 정보 (`UserResponse`) |
| `/flights` | POST | 필요 | 비행편 등록 (`FlightCreate`: flight_id, flight_date, flight_type) → `FlightResponse` |
| `/flights` | GET | 필요 | 내 비행편 목록. 쿼리: `is_active` (bool, 선택) → `FlightListResponse[]` |
| `/flights/{flight_pk}` | GET | 필요 | 비행편 상세 (본인만) → `FlightResponse` |
| `/flights/{flight_pk}` | DELETE | 필요 | 비행편 삭제 (본인만, CASCADE로 로그·알림 포함) |
| `/flights/{flight_pk}/status` | PATCH | 필요 | 모니터링 on/off (`FlightUpdateStatus`: is_active) → `FlightResponse` |
| `/flights/{flight_pk}/refresh` | POST | 필요 | 인천공항 API로 수동 갱신 (본인만) |
| `/flights/{flight_pk}/logs` | GET | **불필요** | 상태 변경 이력. 쿼리: `change_type` (선택: gate_change/delay/status_change/terminal_change) → `FlightStatusLogResponse[]` |
| `/notifications/flights/{flight_pk}` | GET | 불필요 | 해당 비행편 알림 목록 → `NotificationListResponse[]` |
| `/notifications` | GET | 불필요 | 사용자 전체 알림. 쿼리: **`user_email` (필수)**, `notification_type` (선택) → `NotificationResponse[]` |
| `/chatbot/chat` | POST | 불필요 | 챗봇. JSON: `message`, `terminal` (기본 `T1`), `wait_time_hours` (선택) → `ChatResponse` (message, response, mode, sources) |
| `/chatbot` | GET | 불필요 | 챗봇 서비스·환경 변수 안내 JSON |

---

## 참고

- **CORS**: `main.py`에서 `localhost:5173`, `127.0.0.1:5173` 만 허용.
- **스케줄러**: 앱 시작 시 비행편 주기 갱신(기본 10분) — `main.py` `lifespan`.
- **RAG**: `airport_documents` 테이블·`VECTOR_BACKEND` 등은 챗봇 `GET /chatbot` 응답의 `env` 필드와 `README.md`를 참고.
