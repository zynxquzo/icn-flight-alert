# flight_alert/rag/agent/runner.py
"""OpenAI function calling 기반 RAG 에이전트 루프."""

from __future__ import annotations

import logging
import os
from typing import Any

from openai import AsyncOpenAI
from sqlalchemy.orm import Session

from flight_alert.rag.agent.executor import execute_agent_tool
from flight_alert.rag.agent.tools import openai_tool_specs

logger = logging.getLogger(__name__)


def _agent_model() -> str:
    return os.getenv("RAG_AGENT_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"


def _max_tool_rounds() -> int:
    try:
        return max(1, min(10, int(os.getenv("RAG_AGENT_MAX_ROUNDS", "5"))))
    except ValueError:
        return 5


def _wait_str(wait_time_hours: float | int | None) -> str:
    if wait_time_hours is None:
        return "미지정"
    try:
        return str(float(wait_time_hours))
    except (TypeError, ValueError):
        return "미지정"


def _merge_sources(
    acc: dict[str, dict[str, Any]], new_items: list[dict[str, Any]]
) -> None:
    for s in new_items:
        did = s.get("doc_id")
        if did:
            acc[str(did)] = {
                "doc_id": did,
                "title": s.get("title"),
                "source_url": s.get("source_url"),
            }


async def run_rag_agent(
    client: AsyncOpenAI,
    db: Session,
    *,
    user_message: str,
    default_terminal: str,
    wait_time_hours: float | int | None,
) -> tuple[str, list[dict[str, Any]], list[str]]:
    """최종 답변, 출처 목록, 호출된 도구 이름 순서."""
    model = _agent_model()
    max_rounds = _max_tool_rounds()
    tools = openai_tool_specs()

    system = """당신은 인천국제공항 안내 에이전트입니다.

규칙:
1) 사용자 질문에 답하기 전에 반드시 도구 `search_airport_docs`로 문서 DB를 검색하세요. 결과가 부족하면 `relax_terminal=true`로 재검색하거나 `search_airport_docs_keyword`를 사용할 수 있습니다.
2) 도구 결과에 없는 구체적 사실(층·시간·전화 등)은 지어내지 마세요. 없으면 안내 데스크나 공항 공식 채널을 안내하세요.
3) 한국어로 간결·친절하게 답하고, 가능하면 터미널·층·운영시간을 검색 결과에서만 인용하세요.
4) 최종 답변 마지막에 한 줄로 `참고:` 뒤에 사용한 문서 제목을 쉼표로 나열하세요."""

    user_blob = f"""사용자 질문:
{user_message}

컨텍스트:
- 사용자 기본 터미널: {default_terminal}
- 대기 시간(시간): {_wait_str(wait_time_hours)}
"""

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_blob},
    ]

    source_acc: dict[str, dict[str, Any]] = {}
    tool_trace: list[str] = []

    for round_i in range(max_rounds):
        resp = await client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.25,
            max_tokens=1000,
        )
        msg = resp.choices[0].message
        if not msg.tool_calls:
            text = (msg.content or "").strip()
            return text, list(source_acc.values()), tool_trace

        assistant_payload: dict[str, Any] = {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments or "{}",
                    },
                }
                for tc in msg.tool_calls
            ],
        }
        if msg.content:
            assistant_payload["content"] = msg.content
        messages.append(assistant_payload)

        for tc in msg.tool_calls:
            name = tc.function.name
            args = tc.function.arguments or "{}"
            tool_trace.append(name)
            out, srcs = await execute_agent_tool(
                db,
                name,
                args,
                default_terminal=default_terminal,
            )
            _merge_sources(source_acc, srcs)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": out,
                }
            )

        logger.info("RAG agent 라운드 %s/%s 완료", round_i + 1, max_rounds)

    # 상한 도달: 도구 없이 마무리
    messages.append(
        {
            "role": "user",
            "content": (
                "검색·도구 호출은 여기까지입니다. "
                "지금까지의 도구 결과만 근거로 최종 답변을 한국어로 작성하세요. "
                "추가 사실을 만들지 마세요."
            ),
        }
    )
    resp = await client.chat.completions.create(
        model=model,
        messages=messages,
        tool_choice="none",
        temperature=0.25,
        max_tokens=1000,
    )
    text = (resp.choices[0].message.content or "").strip()
    return text, list(source_acc.values()), tool_trace
