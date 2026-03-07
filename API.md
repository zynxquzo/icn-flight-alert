# ICN Flight Alert API Documentation

## 📋 목차
- [개요](#개요)
- [Base URL](#base-url)
- [인증](#인증)
- [공통 응답 형식](#공통-응답-형식)
- [에러 코드](#에러-코드)
- [API 엔드포인트](#api-엔드포인트)
  - [Flights](#flights)
  - [Notifications](#notifications)
  - [Airport Chatbot](#airport-chatbot)

---

## 개요

인천공항 비행편 실시간 모니터링 및 알림 서비스 API

**버전:** v1  
**프로토콜:** REST API  
**응답 형식:** JSON

---

## Base URL

```
Development: http://localhost:8000/api/v1
Production: https://icn-flight-alert.com/api/v1
```

---

## 인증

현재 MVP 버전에서는 인증 없이 이메일 기반으로 동작합니다.

**향후 계획:** JWT 토큰 기반 인증 추가 예정

---

## 공통 응답 형식

### 성공 응답
```json
{
  "success": true,
  "data": { ... },
  "message": "요청이 성공적으로 처리되었습니다"
}
```

### 에러 응답
```json
{
  "success": false,
  "error": {
    "code": "FLIGHT_NOT_FOUND",
    "message": "해당 비행편을 찾을 수 없습니다",
    "details": {}
  }
}
```

---

## 에러 코드

| 코드 | HTTP Status | 설명 |
|------|-------------|------|
| `FLIGHT_NOT_FOUND` | 404 | 비행편을 찾을 수 없음 |
| `INVALID_FLIGHT_NUMBER` | 400 | 잘못된 편명 형식 |
| `INVALID_DATE` | 400 | 잘못된 날짜 형식 |
| `INVALID_EMAIL` | 400 | 잘못된 이메일 형식 |
| `API_ERROR` | 500 | 인천공항 API 호출 실패 |
| `ALREADY_REGISTERED` | 409 | 이미 등록된 비행편 |
| `VALIDATION_ERROR` | 422 | 요청 데이터 검증 실패 |

---

## API 엔드포인트

## Flights

### 1. 비행편 등록

사용자가 관심 비행편을 등록합니다. 등록 시 인천공항 API를 호출하여 초기 상태를 저장합니다.

**Endpoint:** `POST /flights`

**Request Body:**
```json
{
  "user_email": "user@example.com",
  "flight_id": "KE123",
  "flight_date": "2026-03-15",
  "flight_type": "departure"
}
```

**Parameters:**

| 필드 | 타입 | 필수 | 설명 | 예시 |
|------|------|------|------|------|
| user_email | string | ✅ | 알림 받을 이메일 | user@example.com |
| flight_id | string | ✅ | 항공편명 | KE123, VJ974 |
| flight_date | string | ✅ | 출발/도착 날짜 (YYYY-MM-DD) | 2026-03-15 |
| flight_type | string | ✅ | 'departure' 또는 'arrival' | departure |

**Response (201 Created):**
```json
{
  "success": true,
  "data": {
    "flight_pk": 1,
    "user_email": "user@example.com",
    "flight_id": "KE123",
    "flight_date": "2026-03-15",
    "flight_type": "departure",
    "airline": "대한항공",
    "airport": "도쿄",
    "airport_code": "NRT",
    "terminal_id": "P02",
    "gate_number": "253",
    "schedule_date_time": "202603151430",
    "estimated_date_time": "202603151430",
    "remark": "출발",
    "chkin_range": "D01-D10",
    "is_active": true,
    "created_at": "2026-03-07T10:30:00Z",
    "last_checked_at": "2026-03-07T10:30:00Z"
  },
  "message": "비행편이 성공적으로 등록되었습니다"
}
```

---

### 2. 비행편 목록 조회

사용자가 등록한 모든 비행편을 조회합니다.

**Endpoint:** `GET /flights`

**Query Parameters:**

| 필드 | 타입 | 필수 | 설명 | 예시 |
|------|------|------|------|------|
| user_email | string | ✅ | 사용자 이메일 | user@example.com |
| is_active | boolean | ❌ | 활성 상태 필터 | true |
| page | integer | ❌ | 페이지 번호 (기본값: 1) | 1 |
| limit | integer | ❌ | 페이지당 항목 수 (기본값: 10) | 10 |

**Example Request:**
```
GET /flights?user_email=user@example.com&is_active=true&page=1&limit=10
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "flights": [
      {
        "flight_pk": 1,
        "flight_id": "KE123",
        "flight_date": "2026-03-15",
        "flight_type": "departure",
        "airline": "대한항공",
        "airport": "도쿄",
        "gate_number": "253",
        "schedule_date_time": "202603151430",
        "estimated_date_time": "202603151430",
        "remark": "출발",
        "is_active": true
      }
    ],
    "pagination": {
      "total": 5,
      "page": 1,
      "limit": 10,
      "total_pages": 1
    }
  }
}
```

---

### 3. 비행편 상세 조회

특정 비행편의 상세 정보를 조회합니다.

**Endpoint:** `GET /flights/{flight_pk}`

**Path Parameters:**

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| flight_pk | integer | ✅ | 비행편 PK |

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "flight_pk": 1,
    "user_email": "user@example.com",
    "flight_id": "KE123",
    "flight_date": "2026-03-15",
    "flight_type": "departure",
    "airline": "대한항공",
    "airport": "도쿄",
    "airport_code": "NRT",
    "terminal_id": "P02",
    "gate_number": "253",
    "schedule_date_time": "202603151430",
    "estimated_date_time": "202603151445",
    "remark": "지연",
    "chkin_range": "D01-D10",
    "is_active": true,
    "created_at": "2026-03-07T10:30:00Z",
    "last_checked_at": "2026-03-15T12:00:00Z",
    "delay_minutes": 15
  }
}
```

---

### 4. 비행편 상태 수동 갱신

특정 비행편의 상태를 수동으로 갱신합니다. (디버깅/테스트용)

**Endpoint:** `POST /flights/{flight_pk}/refresh`

**Path Parameters:**

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| flight_pk | integer | ✅ | 비행편 PK |

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "flight_pk": 1,
    "changes_detected": true,
    "changes": [
      {
        "field": "gate_number",
        "old_value": "253",
        "new_value": "255",
        "change_type": "gate_change"
      },
      {
        "field": "estimated_date_time",
        "old_value": "202603151430",
        "new_value": "202603151445",
        "change_type": "delay"
      }
    ],
    "updated_at": "2026-03-15T12:05:00Z"
  },
  "message": "비행편 상태가 갱신되었습니다. 2건의 변경사항이 감지되었습니다."
}
```

**No Changes Response:**
```json
{
  "success": true,
  "data": {
    "flight_pk": 1,
    "changes_detected": false,
    "updated_at": "2026-03-15T12:05:00Z"
  },
  "message": "비행편 상태가 갱신되었습니다. 변경사항이 없습니다."
}
```

---

### 5. 비행편 삭제

등록된 비행편을 삭제합니다.

**Endpoint:** `DELETE /flights/{flight_pk}`

**Path Parameters:**

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| flight_pk | integer | ✅ | 비행편 PK |

**Response (200 OK):**
```json
{
  "success": true,
  "message": "비행편이 삭제되었습니다"
}
```

---

### 6. 비행편 모니터링 활성화/비활성화

비행편 모니터링을 활성화하거나 비활성화합니다.

**Endpoint:** `PATCH /flights/{flight_pk}/status`

**Path Parameters:**

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| flight_pk | integer | ✅ | 비행편 PK |

**Request Body:**
```json
{
  "is_active": false
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "flight_pk": 1,
    "is_active": false
  },
  "message": "비행편 모니터링이 비활성화되었습니다"
}
```

---

## Notifications

### 7. 알림 목록 조회

특정 비행편의 알림 이력을 조회합니다.

**Endpoint:** `GET /flights/{flight_pk}/notifications`

**Path Parameters:**

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| flight_pk | integer | ✅ | 비행편 PK |

**Query Parameters:**

| 필드 | 타입 | 필수 | 설명 | 예시 |
|------|------|------|------|------|
| notification_type | string | ❌ | 알림 타입 필터 | delay, gate_change |
| page | integer | ❌ | 페이지 번호 | 1 |
| limit | integer | ❌ | 페이지당 항목 수 | 10 |

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "notifications": [
      {
        "notification_id": 1,
        "flight_pk": 1,
        "notification_type": "gate_change",
        "message": "게이트가 253에서 255로 변경되었습니다",
        "sent_to": "user@example.com",
        "sent_at": "2026-03-15T12:05:00Z",
        "is_sent": true,
        "error_message": null
      },
      {
        "notification_id": 2,
        "flight_pk": 1,
        "notification_type": "delay",
        "message": "출발 시각이 15분 지연되었습니다 (14:30 → 14:45)",
        "sent_to": "user@example.com",
        "sent_at": "2026-03-15T12:05:00Z",
        "is_sent": true,
        "error_message": null
      }
    ],
    "pagination": {
      "total": 2,
      "page": 1,
      "limit": 10,
      "total_pages": 1
    }
  }
}
```

---

### 8. 사용자별 전체 알림 조회

사용자의 모든 비행편에 대한 알림을 조회합니다.

**Endpoint:** `GET /notifications`

**Query Parameters:**

| 필드 | 타입 | 필수 | 설명 | 예시 |
|------|------|------|------|------|
| user_email | string | ✅ | 사용자 이메일 | user@example.com |
| notification_type | string | ❌ | 알림 타입 필터 | delay |
| start_date | string | ❌ | 시작 날짜 (YYYY-MM-DD) | 2026-03-01 |
| end_date | string | ❌ | 종료 날짜 (YYYY-MM-DD) | 2026-03-31 |
| page | integer | ❌ | 페이지 번호 | 1 |
| limit | integer | ❌ | 페이지당 항목 수 | 20 |

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "notifications": [
      {
        "notification_id": 1,
        "flight_pk": 1,
        "flight_id": "KE123",
        "flight_date": "2026-03-15",
        "notification_type": "gate_change",
        "message": "게이트가 253에서 255로 변경되었습니다",
        "sent_to": "user@example.com",
        "sent_at": "2026-03-15T12:05:00Z",
        "is_sent": true
      }
    ],
    "pagination": {
      "total": 5,
      "page": 1,
      "limit": 20,
      "total_pages": 1
    }
  }
}
```

---

### 9. 알림 재전송

전송 실패한 알림을 재전송합니다.

**Endpoint:** `POST /notifications/{notification_id}/resend`

**Path Parameters:**

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| notification_id | integer | ✅ | 알림 ID |

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "notification_id": 1,
    "is_sent": true,
    "sent_at": "2026-03-15T13:00:00Z"
  },
  "message": "알림이 성공적으로 재전송되었습니다"
}
```

---

## Flight Status Logs

### 10. 비행편 변경 이력 조회

특정 비행편의 상태 변경 이력을 조회합니다.

**Endpoint:** `GET /flights/{flight_pk}/logs`

**Path Parameters:**

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| flight_pk | integer | ✅ | 비행편 PK |

**Query Parameters:**

| 필드 | 타입 | 필수 | 설명 | 예시 |
|------|------|------|------|------|
| change_type | string | ❌ | 변경 타입 필터 | gate_change, delay |
| page | integer | ❌ | 페이지 번호 | 1 |
| limit | integer | ❌ | 페이지당 항목 수 | 10 |

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "logs": [
      {
        "log_id": 1,
        "flight_pk": 1,
        "schedule_date_time": "202603151430",
        "estimated_date_time": "202603151445",
        "terminal_id": "P02",
        "gate_number": "255",
        "remark": "지연",
        "carousel": null,
        "change_type": "delay",
        "detected_at": "2026-03-15T12:05:00Z"
      },
      {
        "log_id": 2,
        "flight_pk": 1,
        "schedule_date_time": "202603151430",
        "estimated_date_time": "202603151430",
        "terminal_id": "P02",
        "gate_number": "255",
        "remark": "출발",
        "carousel": null,
        "change_type": "gate_change",
        "detected_at": "2026-03-15T12:00:00Z"
      }
    ],
    "pagination": {
      "total": 2,
      "page": 1,
      "limit": 10,
      "total_pages": 1
    }
  }
}
```

---

## Airport Chatbot

### 11. 공항 대기 챗봇

비행편 정보를 기반으로 공항에서 할 일, 이동 시간, 체크리스트 등을 추천합니다.

**Endpoint:** `POST /chat/airport-helper`

**Request Body:**
```json
{
  "flight_pk": 1,
  "user_message": "지금 공항에 도착했어요. 뭘 해야 할까요?",
  "context": {
    "current_location": "1층 입국장",
    "time_until_departure": 120
  }
}
```

**Parameters:**

| 필드 | 타입 | 필수 | 설명 | 예시 |
|------|------|------|------|------|
| flight_pk | integer | ✅ | 비행편 PK | 1 |
| user_message | string | ✅ | 사용자 질문 | "지금 공항에 도착했어요" |
| context.current_location | string | ❌ | 현재 위치 | "1층 입국장" |
| context.time_until_departure | integer | ❌ | 출발까지 남은 시간(분) | 120 |

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "assistant_message": "안녕하세요! KE123편 (도쿄행)으로 출발 2시간 전이시군요.\n\n지금 해야 할 일:\n1. 체크인 카운터 D01-D10에서 탑승권 발권 (30분 소요)\n2. 보안검색대 통과 (20분 소요)\n3. 출국심사 (15분 소요)\n4. 탑승구 255번으로 이동 (10분 소요)\n\n여유시간이 45분 정도 있으니, 면세점 쇼핑이나 라운지 방문도 가능합니다. 탑승 시작은 출발 30분 전부터입니다.",
    "flight_info": {
      "flight_id": "KE123",
      "airline": "대한항공",
      "destination": "도쿄",
      "gate_number": "255",
      "terminal_id": "P02",
      "departure_time": "14:30",
      "current_status": "정상"
    },
    "recommendations": [
      {
        "action": "체크인",
        "location": "D01-D10 카운터",
        "estimated_time": 30,
        "priority": "high"
      },
      {
        "action": "보안검색",
        "location": "2층 출국장",
        "estimated_time": 20,
        "priority": "high"
      },
      {
        "action": "면세점 쇼핑",
        "location": "탑승동",
        "estimated_time": 30,
        "priority": "low"
      }
    ]
  }
}
```

---

### 12. 채팅 이력 조회

사용자의 챗봇 대화 이력을 조회합니다. (선택 기능)

**Endpoint:** `GET /chat/history`

**Query Parameters:**

| 필드 | 타입 | 필수 | 설명 | 예시 |
|------|------|------|------|------|
| flight_pk | integer | ✅ | 비행편 PK | 1 |
| limit | integer | ❌ | 최근 메시지 수 | 10 |

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "messages": [
      {
        "role": "user",
        "content": "지금 공항에 도착했어요",
        "timestamp": "2026-03-15T10:30:00Z"
      },
      {
        "role": "assistant",
        "content": "안녕하세요! KE123편으로 출발 2시간 전이시군요...",
        "timestamp": "2026-03-15T10:30:05Z"
      }
    ]
  }
}
```

---

## 웹훅 (향후 구현 예정)

### 13. 웹훅 등록

알림을 이메일 대신 웹훅으로 받을 수 있습니다. (향후 기능)

**Endpoint:** `POST /webhooks`

**Request Body:**
```json
{
  "user_email": "user@example.com",
  "webhook_url": "https://your-service.com/webhook",
  "events": ["gate_change", "delay", "cancel"]
}
```

---

## 통계 API (선택 기능)

### 14. 비행편 통계

사용자의 비행편 이용 통계를 제공합니다.

**Endpoint:** `GET /stats/flights`

**Query Parameters:**

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| user_email | string | ✅ | 사용자 이메일 |

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "total_flights": 15,
    "active_flights": 3,
    "total_notifications": 28,
    "notification_breakdown": {
      "delay": 12,
      "gate_change": 10,
      "terminal_change": 3,
      "cancel": 3
    },
    "most_used_airline": "대한항공",
    "most_common_destination": "도쿄"
  }
}
```

---

## 부록

### 날짜/시간 형식

| 필드 | 형식 | 예시 |
|------|------|------|
| flight_date | YYYY-MM-DD | 2026-03-15 |
| schedule_date_time | YYYYMMDDHHmm | 202603151430 |
| created_at, sent_at | ISO 8601 | 2026-03-15T12:05:00Z |

### 알림 타입 (notification_type)

| 값 | 설명 |
|----|------|
| delay | 출발/도착 지연 |
| gate_change | 게이트 변경 |
| terminal_change | 터미널 변경 |
| cancel | 결항 |

### 변경 타입 (change_type)

| 값 | 설명 |
|----|------|
| delay | 시간 지연 |
| gate_change | 게이트 변경 |
| terminal_change | 터미널 변경 |
| status_change | 운항 상태 변경 |

### 비행편 타입 (flight_type)

| 값 | 설명 |
|----|------|
| departure | 출발편 |
| arrival | 도착편 |

### 터미널 코드 (terminal_id)

| 값 | 설명 |
|----|------|
| P01 | 제1여객터미널 |
| P02 | 탑승동 |
| P03 | 제2여객터미널 |
| C01 | 화물터미널 남측 |
| C02 | 화물터미널 북측 |
| C03 | 제2화물터미널 |

