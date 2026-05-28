# flight_alert/services/chatbot_service.py
"""인천공항 안내 챗봇: 레거시 LLM / 단순 RAG / RAG 에이전트(도구 호출) 지원."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

from dotenv import load_dotenv
from openai import AsyncOpenAI, OpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import async_session_maker
from flight_alert.models.flight import Flight
from flight_alert.models.notification import Notification
from flight_alert.rag.agent.runner import run_rag_agent
from flight_alert.repositories import vector_repository
from flight_alert.services.embedding_service import generate_embedding

load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class ChatOutcome:
    """챗봇 1회 응답 결과."""

    response: str
    mode: str  # legacy | rag | agent
    sources: list[dict] = field(default_factory=list)


def _normalize_terminal(terminal: str) -> str:
    t = (terminal or "T1").strip().upper()
    if t in ("1", "T1", "TERMINAL1", "제1", "제1터미널"):
        return "T1"
    if t in ("2", "T2", "TERMINAL2", "제2", "제2터미널"):
        return "T2"
    return t


def _rag_enabled() -> bool:
    return os.getenv("RAG_ENABLED", "true").strip().lower() in ("1", "true", "yes", "on")


def _rag_agent_enabled() -> bool:
    return os.getenv("RAG_AGENT_ENABLED", "true").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _rag_top_k() -> int:
    try:
        return max(1, min(20, int(os.getenv("RAG_TOP_K", "5"))))
    except ValueError:
        return 5


# ---------------------------------------------------------------------------
# 복잡도 분류 — 단순 FAQ → RAG/LEGACY, 복합 질문 → AGENT
# ---------------------------------------------------------------------------
_COMPLEX_PATTERNS = re.compile(
    r"(내\s*비행|내\s*편|내\s*항공|내\s*게이트|내\s*탑승|내\s*터미널"
    r"|KE\d{2,4}|OZ\d{2,4}|LJ\d{2,4}|TW\d{2,4}|7C\d{2,4}|BX\d{2,4}"
    r"|[A-Z]{2}\d{2,4}"  # 편명 패턴
    r"|게이트.*바뀌|변경.*게이트|지연.*언제|취소.*됐|출발.*늦어"
    r"|어떻게.*가야|환승|연결편|최단|최적.*경로"
    r"|\?.*\?)",  # 두 개 이상의 물음표 = 복합 질문
    re.IGNORECASE,
)

_SIMPLE_PATTERNS = re.compile(
    r"^(안녕|하이|hi|hello|감사|고마워|수고|bye|잘\s*가|네|아니|응|ㅇ|ㅋ)",
    re.IGNORECASE,
)


def _is_complex_query(message: str) -> bool:
    """단순 인사·단답은 False, 복합·개인화 질문은 True."""
    msg = message.strip()
    if len(msg) < 10 and _SIMPLE_PATTERNS.match(msg):
        return False
    if _COMPLEX_PATTERNS.search(msg):
        return True
    # 문장이 길거나 다중 질의
    if len(msg) > 80 or msg.count("?") > 1 or msg.count("그리고") > 0:
        return True
    return False


# ---------------------------------------------------------------------------
# 사용자 개인화 컨텍스트 빌더
# ---------------------------------------------------------------------------
async def _build_user_context(db: AsyncSession, user_id: int) -> str:
    """사용자의 등록 비행편 + 최근 알림 5건을 컨텍스트 문자열로 반환."""
    flights_result = await db.execute(
        select(Flight)
        .where(Flight.user_id == user_id, Flight.is_active == True)  # noqa: E712
        .order_by(Flight.created_at.desc())
        .limit(5)
    )
    flights: list[Flight] = list(flights_result.scalars().all())

    notif_result = await db.execute(
        select(Notification)
        .join(Flight, Notification.flight_pk == Flight.flight_pk)
        .where(Flight.user_id == user_id)
        .order_by(Notification.sent_at.desc())
        .limit(5)
    )
    notifications: list[Notification] = list(notif_result.scalars().all())

    if not flights and not notifications:
        return ""

    lines: list[str] = ["<사용자 등록 비행편>"]
    for f in flights:
        gate = f.gate_number or "미정"
        terminal = f.terminal_id or "미정"
        remark = f.remark or "-"
        lines.append(
            f"- {f.flight_id} ({f.flight_date}) | 터미널 {terminal} | 게이트 {gate} | 상태: {remark}"
        )

    if notifications:
        lines.append("<최근 알림>")
        for n in notifications:
            lines.append(f"- [{n.notification_type.value}] {n.message}")

    return "\n".join(lines)


class ChatbotService:
    """OpenAI + 선택적 RAG / RAG 에이전트"""

    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY가 설정되지 않았습니다")
            self.client = None
            self.async_client = None
        else:
            self.client = OpenAI(api_key=api_key)
            self.async_client = AsyncOpenAI(api_key=api_key)

    def _create_system_prompt(
        self,
        terminal: str,
        wait_time_hours: float | int | None,
        user_context: str = "",
    ) -> str:
        base_prompt = """당신은 인천국제공항 안내 도우미입니다.

역할:
- 공항에서 대기하는 승객들에게 유용한 정보 제공
- 식사, 쇼핑, 휴식 공간, 편의시설 추천
- 사용자의 등록 비행편 정보가 있으면 개인화된 답변 제공
- 친절하고 간결하게 답변

주의사항:
- 구체적이고 실용적인 정보 제공
- 한국어로 답변
- 3-5문장으로 간결하게
- 이모지 적절히 사용 (✈️🍽️🛍️☕)
"""
        terminal_info = f"\n현재 위치: 인천공항 {terminal}"
        time_info = ""
        if wait_time_hours is not None:
            try:
                w = float(wait_time_hours)
            except (TypeError, ValueError):
                w = None
            if w is not None:
                time_info = f"\n대기 시간: 약 {w}시간"
                if w >= 3:
                    time_info += "\n추천: 충분한 시간이 있으니 여유롭게 둘러보세요."
                elif w >= 1:
                    time_info += "\n추천: 간단한 식사나 쇼핑을 즐기세요."
                else:
                    time_info += "\n추천: 시간이 촉박하니 게이트 근처에서 대기하세요."

        ctx_section = f"\n\n{user_context}" if user_context else ""
        return base_prompt + terminal_info + time_info + ctx_section

    def _chat_legacy(
        self,
        message: str,
        terminal: str,
        wait_time_hours: float | int | None,
        user_context: str = "",
    ) -> ChatOutcome:
        if not self.client:
            return ChatOutcome(
                response="죄송합니다. 챗봇 서비스가 현재 이용 불가능합니다.",
                mode="legacy",
            )
        try:
            system_prompt = self._create_system_prompt(terminal, wait_time_hours, user_context)
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message},
                ],
                temperature=0.7,
                max_tokens=500,
            )
            answer = response.choices[0].message.content or ""
            logger.info("챗봇(레거시) 응답 생성 성공: %s 글자", len(answer))
            return ChatOutcome(response=answer, mode="legacy")
        except Exception as e:
            logger.error("챗봇 응답 생성 실패: %s", e)
            return ChatOutcome(
                response="죄송합니다. 응답 생성 중 오류가 발생했습니다.",
                mode="legacy",
            )

    async def _chat_rag(
        self,
        db: AsyncSession,
        message: str,
        terminal: str,
        wait_time_hours: float | int | None,
        user_context: str = "",
    ) -> ChatOutcome:
        assert self.async_client is not None
        try:
            if await vector_repository.count_documents(db) == 0:
                return self._chat_legacy(message, terminal, wait_time_hours, user_context)

            query_emb = await generate_embedding(message)
            term = _normalize_terminal(terminal)
            top_k = _rag_top_k()

            docs = await vector_repository.search_hybrid_documents(
                db, query_emb, message, top_k=top_k, terminal=term
            )
            if not docs:
                docs = await vector_repository.search_hybrid_documents(
                    db, query_emb, message, top_k=top_k, terminal=None
                )

            sources = [
                {"doc_id": d.doc_id, "title": d.title, "source_url": d.source_url}
                for d in docs
            ]

            context_parts: list[str] = []
            for doc in docs:
                loc = " ".join(
                    x for x in (doc.terminal, doc.floor, doc.area, doc.zone) if x
                )
                line = (
                    f"[{doc.title}]\n{doc.content}\n"
                    f"위치: {loc or '상세 위치는 문의 또는 안내 데스크 확인'}\n"
                    f"운영시간: {doc.hours or '별도 안내'}"
                )
                if doc.contact:
                    line += f"\n연락처: {doc.contact}"
                context_parts.append(line)
            context = "\n\n".join(context_parts)

            w_str = "미지정"
            if wait_time_hours is not None:
                try:
                    w_str = str(float(wait_time_hours))
                except (TypeError, ValueError):
                    pass

            user_prompt = f"""아래 <공항 정보>를 우선 근거로 사용자 질문에 답하세요.
<공항 정보>에 없는 내용은 일반적인 공항 이용 팁으로만 짧게 보완하고, 확실하지 않으면 모른다고 하세요.

<공항 정보>
{context}

{user_context}

<사용자 질문>
{message}

<추가 정보>
- 터미널: {term}
- 대기 시간(시간): {w_str}
"""
            response = await self.async_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "당신은 인천국제공항 안내 챗봇입니다. "
                            "제공된 공항 정보를 바탕으로 한국어로 정확하고 친절하게 답변합니다."
                        ),
                    },
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.4,
                max_tokens=700,
            )
            answer = response.choices[0].message.content or ""
            logger.info("챗봇(RAG) 응답 생성 성공: %s 글자", len(answer))
            return ChatOutcome(response=answer, mode="rag", sources=sources)
        except Exception as e:
            logger.error("RAG 응답 실패, 레거시로 폴백: %s", e)
            return self._chat_legacy(message, terminal, wait_time_hours, user_context)

    async def _chat_rag_agent(
        self,
        db: AsyncSession,
        message: str,
        terminal: str,
        wait_time_hours: float | int | None,
        user_context: str = "",
    ) -> ChatOutcome:
        assert self.async_client is not None
        term = _normalize_terminal(terminal)
        try:
            text, sources, trace = await run_rag_agent(
                self.async_client,
                db,
                user_message=message,
                default_terminal=term,
                wait_time_hours=wait_time_hours,
                user_context=user_context,
            )
            logger.info("챗봇(RAG agent) 완료 tools=%s sources=%s", trace, len(sources))
            if not (text or "").strip():
                return await self._chat_rag(db, message, terminal, wait_time_hours, user_context)
            return ChatOutcome(response=text, mode="agent", sources=sources)
        except Exception as e:
            logger.error("RAG agent 실패, 단순 RAG로 폴백: %s", e)
            return await self._chat_rag(db, message, terminal, wait_time_hours, user_context)

    async def chat(
        self,
        message: str,
        terminal: str = "T1",
        wait_time_hours: float | int | None = None,
        user_id: int | None = None,
    ) -> ChatOutcome:
        if not self.async_client or not self.client:
            return ChatOutcome(
                response="죄송합니다. 챗봇 서비스가 현재 이용 불가능합니다.",
                mode="legacy",
            )

        async with async_session_maker() as db:
            # 사용자 개인화 컨텍스트 (로그인 상태이고 복합 질문일 때만)
            user_context = ""
            if user_id and _is_complex_query(message):
                try:
                    user_context = await _build_user_context(db, user_id)
                except Exception as e:
                    logger.warning("사용자 컨텍스트 빌드 실패: %s", e)

            if not _rag_enabled():
                return self._chat_legacy(message, terminal, wait_time_hours, user_context)

            has_docs = await vector_repository.count_documents(db) > 0
            if not has_docs:
                return self._chat_legacy(message, terminal, wait_time_hours, user_context)

            # 복잡도 기반 라우팅
            if _rag_agent_enabled() and _is_complex_query(message):
                return await self._chat_rag_agent(
                    db, message, terminal, wait_time_hours, user_context
                )

            return await self._chat_rag(db, message, terminal, wait_time_hours, user_context)


chatbot_service = ChatbotService()
