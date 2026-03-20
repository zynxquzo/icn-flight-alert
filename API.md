# 📝 API

| url | method | 관련 |
|-----|--------|------|
| `/auth/signup` | POST | 회원가입 |
| `/auth/login` | POST | 로그인 |
| `/me` | GET | 내 정보 조회 |
| `/flights` | POST | 비행편 등록 |
| `/flights` | GET | 내 비행편 목록 조회 |
| `/flights/{flight_pk}` | GET | 비행편 상세 조회 |
| `/flights/{flight_pk}` | DELETE | 비행편 삭제 |
| `/flights/{flight_pk}/status` | PATCH | 비행편 활성화/비활성화 |
| `/flights/{flight_pk}/refresh` | POST | 비행편 수동 갱신 |
| `/flights/{flight_pk}/logs` | GET | 비행편 변경 이력 조회 |
| `/notifications` | GET | 알림 목록 조회 |
| `/chatbot/chat` | POST | AI 챗봇 |
| `/chatbot/` | GET | 챗봇 정보 |