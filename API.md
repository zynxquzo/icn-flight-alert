# ICN Flight Alert — API 명세서 (API Specification)

> **Base URL**: 배포 환경에 따라 설정 (로컬 예: `http://127.0.0.1:8000`)  
> **인증 방식**: Bearer Token (JWT), 엔드포인트별 상이 (아래 각 절 참고)  
> **응답 형식**: JSON  
> **문자 인코딩**: UTF-8 (문서·요청 본문은 UTF-8 권장)  
> **OpenAPI**: `/docs` (Swagger UI), `/redoc`

애플리케이션 엔트리: `main.py`. DB는 PostgreSQL (`DATABASE_URL`), 스키마는 `flight_alert/models/` 와 대응합니다.

---

## 목차

1. [공통 규칙](#1-공통-규칙)
2. [헬스 (Health)](#2-헬스-health)
3. [인증 (Authentication)](#3-인증-authentication)
4. [사용자 (User)](#4-사용자-user)
5. [비행편 (Flights)](#5-비행편-flights)
6. [알림 (Notifications)](#6-알림-notifications)
7. [챗봇 (Chatbot)](#7-챗봇-chatbot)
8. [부록: 열거형·참고](#8-부록-열거형참고)

---

## 1. 공통 규칙

### 1.1 성공 응답 형태

대부분의 엔드포인트는 **FastAPI / Pydantic 기본 동작**에 따라, `success` / `data` 래핑 없이 **응답 모델 필드가 곧 JSON 루트 객체**입니다.

**예시 (회원가입 201 응답 본문)**:

```json
{
  "user_id": 1,
  "email": "user@example.com",
  "created_at": "2026-04-15T10:00:00"
}
```

**예시 (비행편 목록 200)**:

```json
[
  {
    "flight_pk": 10,
    "flight_id": "KE123",
    "flight_date": "2026-05-01",
    "flight_type": "departure",
    "airline": "대한항공",
    "airport": "나리타",
    "gate_number": "114",
    "schedule_date_time": "202605011030",
    "estimated_date_time": "202605011045",
    "remark": "출발",
    "is_active": true
  }
]
```

`POST /flights/{flight_pk}/refresh` 만 객체 형태가 서비스 반환값에 맞춰 고정 필드(`flight_pk`, `changes_detected`, `changes`, `updated_at`)를 사용합니다.

### 1.2 오류 응답 형태

**A) `HTTPException` 및 FastAPI 요청 검증 오류**

```json
{
  "detail": "이메일 또는 비밀번호가 올바르지 않습니다."
}
```

검증 오류 시 `detail`은 문자열 배열 등 **배열 형태**일 수 있습니다.

**B) 애플리케이션 커스텀 예외** (`flight_alert/exception_handlers.py`)

```json
{
  "success": false,
  "error": {
    "code": "NOT_FOUND",
    "message": "리소스를 찾을 수 없습니다."
  }
}
```

`code` 예: `NOT_FOUND`, `BAD_REQUEST`, `EXTERNAL_API_ERROR`, `INTERNAL_SERVER_ERROR`.

**C) Bearer JWT 검증 실패** (`HTTPBearer` + `get_current_user`가 적용된 보호 라우트)

```json
{
  "success": false,
  "error": {
    "code": "TOKEN_EXPIRED",
    "message": "토큰이 만료되었습니다."
  }
}
```

`error.code` 예: `TOKEN_MISSING` (헤더 없음·Bearer 없음), `TOKEN_EXPIRED`, `TOKEN_INVALID`, `TOKEN_REVOKED` (로그아웃으로 블랙리스트 등록된 토큰).

### 1.3 공통 HTTP 상태 코드

| 코드 | 설명 |
| :--- | :--- |
| **200 OK** | 조회·수정 성공 |
| **201 Created** | 리소스 생성 성공 |
| **204 No Content** | 삭제 등 본문 없는 성공 |
| **400 Bad Request** | 잘못된 요청 (`BadRequestException` 또는 검증 실패) |
| **401 Unauthorized** | JWT 누락·무효, 로그인 실패 |
| **403 Forbidden** | 타인의 비행편 접근 등 |
| **404 Not Found** | 리소스 없음 (`NotFoundException` 등) |
| **409 Conflict** | 이메일 중복(회원가입) |
| **422 Unprocessable Entity** | Pydantic 필드 검증 실패 |
| **502 Bad Gateway** | 외부 API 오류 (`APIException`) |
| **500 Internal Server Error** | 기타 예상치 못한 서버 오류 |

### 1.4 인증이 필요한 API

헤더:

```
Authorization: Bearer {access_token}
```

**인증 필요**: `/me`, `POST /auth/logout`, `GET /notifications`, `GET /notifications/flights/{flight_pk}`, `POST /notifications/flights/{flight_pk}/check`, `POST/GET/PATCH/DELETE /flights...`, `GET /flights/{flight_pk}/logs`, `GET /chatbot`, `POST /chatbot/chat`.

**인증 불필요**: `/`, `/health`, `/auth/signup`, `/auth/login`.

### 1.5 CORS

`main.py` 기준 허용 출처: `http://localhost:5173`, `http://127.0.0.1:5173`.

---

## 2. 헬스 (Health)

### 2.1 루트 헬스 체크

**Endpoint**: `GET /`

**설명**: 서비스 가동 여부와 문서 경로 안내.

**Response (200)**:

```json
{
  "status": "ok",
  "message": "ICN Flight Alert API가 실행 중입니다.",
  "docs": "/docs"
}
```

---

### 2.2 헬스 체크 (확장)

**Endpoint**: `GET /health`

**설명**: 프로세스 가동 여부와 함께 DB·Redis·스케줄러 상태를 확인합니다. 요청마다 `X-Request-ID` 헤더가 응답에 포함됩니다(미전송 시 서버가 UUID 생성).

**Response (200)**:

```json
{
  "status": "healthy",
  "timestamp": "2026-05-22T12:00:00+00:00",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "checks": {
    "database": { "status": "ok" },
    "redis": { "status": "ok" },
    "scheduler": {
      "enabled": true,
      "running": true,
      "interval_minutes": 10,
      "last_run_at": "2026-05-22T11:50:00+00:00",
      "last_run_status": "ok",
      "leader_lock": true,
      "is_leader": true
    }
  }
}
```

| `checks.*.status` | 설명 |
| :--- | :--- |
| `ok` | 정상 |
| `skipped` | Redis 미설정 등으로 검사 생략 |
| `fail` | 연결·실행 실패 (`status`가 `unhealthy`로 올라갈 수 있음) |

`scheduler.last_run_status`: `ok` \| `error` \| `skipped` (리더가 아닌 인스턴스에서 job 스킵 시 `skipped`).

---

## 3. 인증 (Authentication)

### 3.1 회원가입

**Endpoint**: `POST /auth/signup`

**설명**: 이메일·비밀번호로 계정을 생성합니다.

**Request Body**:

```json
{
  "email": "user@example.com",
  "password": "secretpassword"
}
```

| 필드 | 타입 | 필수 | 설명 |
| :--- | :--- | :--- | :--- |
| `email` | string (이메일) | 예 | `EmailStr` |
| `password` | string | 예 | 평문 (서버에서 bcrypt 해시 저장) |

**Response (201)**: `UserResponse` — `user_id`, `email`, `created_at`.

#### 에러 응답 (Error Response)

| 상태 코드 | 형태 | 메시지 예 | 발생 상황 |
| :--- | :--- | :--- | :--- |
| **409** | `{"detail": "..."}` | 이미 등록된 이메일입니다. | 동일 이메일 가입 시도 |
| **422** | `{"detail": [...]}` | 필드 검증 메시지 | 이메일 형식 오류 등 |

---

### 3.2 로그인

**Endpoint**: `POST /auth/login`

**설명**: 이메일·비밀번호 확인 후 JWT `access_token`을 발급합니다.

**Request Body**:

```json
{
  "email": "user@example.com",
  "password": "secretpassword"
}
```

**Response (200)**: `TokenResponse`

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

| 필드 | 설명 |
| :--- | :--- |
| `access_token` | JWT 문자열 |
| `token_type` | 기본값 `bearer` |

#### 에러 응답 (Error Response)

| 상태 코드 | 메시지 예 | 발생 상황 |
| :--- | :--- | :--- |
| **401** | 이메일 또는 비밀번호가 올바르지 않습니다. | 사용자 없음 또는 비밀번호 불일치 |

---

### 3.3 로그아웃

**Endpoint**: `POST /auth/logout`

**설명**: 현재 `Authorization: Bearer` 토큰의 `jti`를 블랙리스트에 올려, 만료 시각까지 재사용할 수 없게 합니다. `REDIS_URL`이 설정되면 Redis에 `jwt:blacklist:{jti}` 키로 TTL 저장되어 **다중 인스턴스**에서도 무효화가 공유됩니다. 클라이언트는 응답 후 로컬에 저장한 토큰도 삭제하는 것을 권장합니다.

**Headers**:

```
Authorization: Bearer {access_token}
```

**Response (204)**: 본문 없음.

#### 에러 응답 (Error Response)

| 상태 코드 | 형태 | 발생 상황 |
| :--- | :--- | :--- |
| **401** | **C)** 형식 (`TOKEN_MISSING` 등) | Bearer 없음·형식 오류 |
| **401** | **C)** 형식 (`TOKEN_EXPIRED` 등) | 토큰 만료·무효 |

> **운영 참고**: 프로덕션·다중 워커에서는 **`REDIS_URL` 필수**입니다. 미설정 시 인메모리 폴백(단일 인스턴스·로컬 개발용)으로 동작합니다.

---

## 4. 사용자 (User)

### 4.1 내 정보 조회

**Endpoint**: `GET /me`

**설명**: JWT로 식별된 현재 사용자 정보를 반환합니다.

**Headers**:

```
Authorization: Bearer {access_token}
```

**Response (200)**: `UserResponse`

```json
{
  "user_id": 1,
  "email": "user@example.com",
  "created_at": "2026-04-15T10:00:00"
}
```

#### 에러 응답 (Error Response)

| 상태 코드 | 발생 상황 |
| :--- | :--- |
| **401** | 토큰 없음·만료·무효·로그아웃 (`HTTPBearer` / `UnauthorizedException`)|

---

## 5. 비행편 (Flights)

모든 경로는 라우터 prefix **`/flights`** 입니다.  
`{flight_pk}` 는 정수 PK입니다.

---

### 5.1 비행편 등록

**Endpoint**: `POST /flights`

**설명**: 편명·날짜·출발/도착 타입으로 등록합니다. 인천공항 OpenAPI로 실제 편을 조회한 뒤 DB에 저장합니다.

**Headers**:

```
Authorization: Bearer {access_token}
```

**Request Body**: `FlightCreate`

```json
{
  "flight_id": "KE123",
  "flight_date": "2026-05-01",
  "flight_type": "departure"
}
```

| 필드 | 타입 | 필수 | 설명 |
| :--- | :--- | :--- | :--- |
| `flight_id` | string | 예 | 2~10자 (예: `KE123`) |
| `flight_date` | string (date) | 예 | `YYYY-MM-DD` |
| `flight_type` | string | 예 | `departure` \| `arrival` |

**Response (201)**: `FlightResponse` (비행편 상세 필드 전체. `user_id`·`user_email`은 로그인 사용자 기준으로 설정됨).

#### 에러 응답 (Error Response)

| 상태 코드 | 발생 상황 |
| :--- | :--- |
| **401** | 미인증 |
| **400 / 404 / 502** | 공항 API 조회 실패 등 (서비스·외부 API에 따라 상이) |

---

### 5.2 내 비행편 목록 조회

**Endpoint**: `GET /flights`

**설명**: 로그인 사용자 소유 비행편만 조회합니다.

**Headers**:

```
Authorization: Bearer {access_token}
```

**Query Parameters**:

| 이름 | 타입 | 필수 | 설명 |
| :--- | :--- | :--- | :--- |
| `is_active` | boolean | 아니오 | `true` / `false` 로 모니터링 활성 여부 필터 |

**Response (200)**: `FlightListResponse[]` (배열 JSON).

---

### 5.3 비행편 상세 조회

**Endpoint**: `GET /flights/{flight_pk}`

**설명**: 단일 비행편 상세. **본인 소유만** 허용.

**Headers**:

```
Authorization: Bearer {access_token}
```

**Path Parameters**:

| 이름 | 타입 | 필수 | 설명 |
| :--- | :--- | :--- | :--- |
| `flight_pk` | integer | 예 | 비행편 PK |

**Response (200)**: `FlightResponse`.

#### 에러 응답 (Error Response)

| 상태 코드 | `detail` 예 | 발생 상황 |
| :--- | :--- | :--- |
| **403** | 본인의 비행편만 조회할 수 있습니다. | 다른 사용자의 `flight_pk` |
| **404** | (NotFound 등) | 존재하지 않는 PK |

---

### 5.4 비행편 삭제

**Endpoint**: `DELETE /flights/{flight_pk}`

**설명**: 비행편 삭제. 관련 **상태 로그·알림은 DB CASCADE** 로 함께 삭제됩니다.

**Headers**:

```
Authorization: Bearer {access_token}
```

**Path Parameters**:

| 이름 | 타입 | 필수 | 설명 |
| :--- | :--- | :--- | :--- |
| `flight_pk` | integer | 예 | 비행편 PK |

**Response (204)**: 본문 없음.

#### 에러 응답 (Error Response)

| 상태 코드 | 발생 상황 |
| :--- | :--- |
| **403** | 타인 비행편 |
| **404** | 없는 PK |

---

### 5.5 비행편 활성화 상태 변경

**Endpoint**: `PATCH /flights/{flight_pk}/status`

**설명**: 스케줄러 모니터링 on/off (`is_active`).

**Headers**:

```
Authorization: Bearer {access_token}
```

**Path Parameters**:

| 이름 | 타입 | 필수 |
| :--- | :--- | :--- |
| `flight_pk` | integer | 예 |

**Request Body**: `FlightUpdateStatus`

```json
{
  "is_active": false
}
```

**Response (200)**: `FlightResponse`.

#### 에러 응답 (Error Response)

| 상태 코드 | 발생 상황 |
| :--- | :--- |
| **403** | 타인 비행편 |

---

### 5.6 비행편 수동 갱신

**Endpoint**: `POST /flights/{flight_pk}/refresh`

**설명**: 인천공항 API로 즉시 갱신하고, 게이트·터미널·지연·상태(결항 시 알림) 등 변경을 감지해 로그·알림·메일을 처리합니다. 동일 처리는 **`POST /notifications/flights/{flight_pk}/check`**(6.2)에서도 호출할 수 있습니다.

**Headers**:

```
Authorization: Bearer {access_token}
```

**Path Parameters**:

| 이름 | 타입 | 필수 |
| :--- | :--- | :--- |
| `flight_pk` | integer | 예 |

**Response (200)** (본문은 서비스에서 반환하는 `dict`):

```json
{
  "flight_pk": 10,
  "changes_detected": true,
  "changes": [
    {
      "field": "gate_number",
      "old_value": "109",
      "new_value": "114",
      "change_type": "gate_change"
    }
  ],
  "updated_at": "2026-04-15T12:00:00"
}
```

| 필드 | 설명 |
| :--- | :--- |
| `changes_detected` | 변경 1건 이상 여부 |
| `changes` | 변경 메타 배열 (`field`, `old_value`, `new_value`, `change_type`) |
| `updated_at` | 갱신 시각 (`last_checked_at`) |

#### 에러 응답 (Error Response)

| 상태 코드 | 발생 상황 |
| :--- | :--- |
| **403** | 타인 비행편 |

---

### 5.7 비행편 상태 변경 이력 조회

**Endpoint**: `GET /flights/{flight_pk}/logs`

**설명**: 해당 비행편의 `FlightStatusLog` 목록. **로그인 필수**, 본인 소유 비행편만 조회 가능합니다.

**Headers**:

```
Authorization: Bearer {access_token}
```

**Path Parameters**:

| 이름 | 타입 | 필수 |
| :--- | :--- | :--- |
| `flight_pk` | integer | 예 |

**Query Parameters**:

| 이름 | 타입 | 필수 | 설명 |
| :--- | :--- | :--- | :--- |
| `change_type` | string | 아니오 | `gate_change`, `delay`, `status_change`, `terminal_change` 중 하나로 필터 |

**Response (200)**: `FlightStatusLogResponse[]`.

```json
[
  {
    "log_id": 1,
    "flight_pk": 10,
    "schedule_date_time": "202605011030",
    "estimated_date_time": "202605011045",
    "terminal_id": "P01",
    "gate_number": "114",
    "remark": "출발",
    "carousel": null,
    "change_type": "gate_change",
    "detected_at": "2026-04-15T12:00:00"
  }
]
```

#### 에러 응답 (Error Response)

| 상태 코드 | 발생 상황 |
| :--- | :--- |
| **401** | 미인증·토큰 만료 등 (§1.2 C) |
| **403** | 타인 소유 비행편 로그 조회 시도 |

---

## 6. 알림 (Notifications)

라우터 prefix: **`/notifications`**.

---

### 6.1 비행편별 알림 이력 조회

**Endpoint**: `GET /notifications/flights/{flight_pk}`

**설명**: 해당 `flight_pk`에 연결된 **저장된 알림 이력**을 수동 조회합니다. **로그인 필수**, 해당 비행편 소유자만 호출할 수 있습니다. 인천공항 API로 즉시 변경을 확인하려면 §6.2를 사용하세요.

**Headers**:

```
Authorization: Bearer {access_token}
```

**Path Parameters**:

| 이름 | 타입 | 필수 |
| :--- | :--- | :--- |
| `flight_pk` | integer | 예 |

**Response (200)**: `NotificationListResponse[]`.

```json
[
  {
    "notification_id": 1,
    "flight_pk": 10,
    "notification_type": "gate_change",
    "message": "게이트가 109에서 114로 변경되었습니다",
    "sent_at": "2026-04-15T12:00:00",
    "is_sent": true
  }
]
```

#### 에러 응답 (Error Response)

| 상태 코드 | 발생 상황 |
| :--- | :--- |
| **401** | 미인증·토큰 만료 등 (§1.2 C) |
| **403** | 타인 소유 `flight_pk` 알림 조회 시도 |

---

### 6.2 비행편 알림 수동 감지

**Endpoint**: `POST /notifications/flights/{flight_pk}/check`

**설명**: 인천공항 API로 해당 비행편을 **즉시 확인**하고, 게이트·터미널·지연·결항 등 변경을 감지해 `FlightStatusLog`·`Notification` 저장 및 이메일 발송을 수행합니다. **로그인 필수**, 해당 비행편 소유자만 호출할 수 있습니다.

**처리 내용**은 `POST /flights/{flight_pk}/refresh`(§5.6)와 **동일**합니다(`flight_service.refresh_flight` 재사용).

**Headers**:

```
Authorization: Bearer {access_token}
```

**Path Parameters**:

| 이름 | 타입 | 필수 |
| :--- | :--- | :--- |
| `flight_pk` | integer | 예 |

**Response (200)**: §5.6과 동일한 `dict` (`flight_pk`, `changes_detected`, `changes`, `updated_at`).

```json
{
  "flight_pk": 10,
  "changes_detected": true,
  "changes": [
    {
      "field": "gate_number",
      "old_value": "109",
      "new_value": "114",
      "change_type": "gate_change"
    }
  ],
  "updated_at": "2026-04-15T12:00:00"
}
```

| 필드 | 설명 |
| :--- | :--- |
| `changes_detected` | 변경 1건 이상 여부 |
| `changes` | 변경 메타 배열 (`field`, `old_value`, `new_value`, `change_type`) |
| `updated_at` | 갱신 시각 (`last_checked_at`) |

#### 에러 응답 (Error Response)

| 상태 코드 | 발생 상황 |
| :--- | :--- |
| **401** | 미인증·토큰 만료 등 (§1.2 C) |
| **403** | 타인 소유 `flight_pk`에 대한 알림 감지 시도 |

---

### 6.3 로그인 사용자 알림 이력 조회

**Endpoint**: `GET /notifications`

**설명**: JWT로 식별된 사용자 이메일 기준으로, 등록한 비행편들에 대한 **저장된 알림 이력**을 수동 조회합니다.

**Headers**:

```
Authorization: Bearer {access_token}
```

**Query Parameters**:

| 이름 | 타입 | 필수 | 설명 |
| :--- | :--- | :--- | :--- |
| `notification_type` | string | 아니오 | `delay`, `gate_change`, `cancel`, `terminal_change` |

**Response (200)**: `NotificationResponse[]`.

```json
[
  {
    "notification_id": 1,
    "flight_pk": 10,
    "notification_type": "gate_change",
    "message": "게이트가 109에서 114로 변경되었습니다",
    "sent_to": "user@example.com",
    "sent_at": "2026-04-15T12:00:00",
    "is_sent": true,
    "error_message": null
  }
]
```

#### 에러 응답 (Error Response)

| 상태 코드 | 발생 상황 |
| :--- | :--- |
| **401** | 미인증·토큰 만료 등 |

---

## 7. 챗봇 (Chatbot)

라우터 prefix: **`/chatbot`**.

---

### 7.1 챗봇 대화

**Endpoint**: `POST /chatbot/chat`

**설명**: 공항 안내 대화. RAG/에이전트 설정에 따라 `mode`, `sources`가 채워집니다. **로그인 필수**(OpenAI 비용·남용 방지).

**Headers**:

```
Authorization: Bearer {access_token}
```

**Request Body**:

```json
{
  "message": "3시간 기다려야 하는데 뭐하면 좋을까요?",
  "terminal": "T1",
  "wait_time_hours": 3
}
```

| 필드 | 타입 | 필수 | 설명 |
| :--- | :--- | :--- | :--- |
| `message` | string | 예 | 사용자 질문 |
| `terminal` | string | 아니오 | 기본 `T1` |
| `wait_time_hours` | number | 아니오 | 대기 시간(시간) |

**Response (200)**:

```json
{
  "message": "3시간 기다려야 하는데 뭐하면 좋을까요?",
  "response": "…답변 본문…",
  "mode": "agent",
  "sources": [
    {
      "doc_id": "…",
      "title": "…",
      "source_url": "https://…"
    }
  ]
}
```

| 필드 | 설명 |
| :--- | :--- |
| `mode` | `legacy` \| `rag` \| `agent` 등 (구현 기준) |
| `sources` | 근거 문서 메타 배열 (없으면 빈 배열) |

#### 에러 응답 (Error Response)

| 상태 코드 | 발생 상황 |
| :--- | :--- |
| **401** | 미인증·토큰 만료 등 (§1.2 C) |

---

### 7.2 챗봇 서비스 정보

**Endpoint**: `GET /chatbot`

**설명**: 서비스 소개, 기능 목록, RAG 관련 **환경 변수 키** 안내 JSON을 반환합니다. **로그인 필수**.

**Headers**:

```
Authorization: Bearer {access_token}
```

**Response (200)**: 고정 구조 객체 (`service`, `description`, `features`, `env` 등). 상세 키는 구현(`chatbot_router.py`) 기준으로 변할 수 있으므로 운영 시 실제 응답 또는 `/docs` 스키마를 참고하세요.

#### 에러 응답 (Error Response)

| 상태 코드 | 발생 상황 |
| :--- | :--- |
| **401** | 미인증·토큰 만료 등 (§1.2 C) |

---

## 8. 부록: 열거형·참고

### 비행편 타입 (`flight_type`)

- `departure`: 출발
- `arrival`: 도착

### 알림 타입 (`notification_type`)

- `delay`
- `gate_change`
- `cancel`
- `terminal_change`

### 상태 로그 필터 (`change_type`, 로그 조회)

- `gate_change`
- `delay`
- `status_change`
- `terminal_change`

### 기타

- **JWT**: `JWT_SECRET_KEY`(필수), `JWT_ALGORITHM`(기본 `HS256`), `JWT_EXPIRE_MINUTES`(기본 `30`). `jti`는 `POST /auth/logout` 시 블랙리스트 등록 — **`REDIS_URL` 설정 시 Redis 공유**, 미설정 시 인메모리.
- **Redis**: `REDIS_URL` — JWT 블랙리스트·스케줄러 리더 락(`SCHEDULER_LEADER_LOCK`, 기본 true).
- **스케줄러**: `ENABLE_SCHEDULER`(기본 true), `SCHEDULER_INTERVAL_MINUTES`(기본 10). Redis 리더 락으로 **한 인스턴스만** 주기 job 실행.
- **관측**: `LOG_JSON`, `LOG_LEVEL`, `SENTRY_DSN`, `SENTRY_ENVIRONMENT`, `SENTRY_TRACES_SAMPLE_RATE`. 요청 `X-Request-ID` 헤더 지원.
- **RAG 문서**: 테이블 `airport_documents`, `VECTOR_BACKEND`, `CHROMA_*` 등은 `README.md` 및 `GET /chatbot` 의 `env` 설명 참고.
