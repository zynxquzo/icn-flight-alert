"""RAG 도입 전(legacy LLM 단독) / 후(RAG) 응답의 공식 문서 근거 일치율(grounding rate)을 측정.

인천공항 공식 사이트(airport.kr)를 크롤링해 Chroma에 인덱싱한 문서(source_type=official_website)
중 위치 정보가 명확한 시설 18곳을 골라 "정확히 어디에 있어?" 질문을 만들고,
- legacy 모드(RAG_ENABLED=false): OpenAI 모델 단독 응답
- rag 모드(RAG_ENABLED=true): Chroma에서 검색한 공식 문서를 근거로 응답
두 응답에서 (1) 정답 위치 키워드 포함 여부, (2) 응답이 언급한 층수가 실제 층수와
일치하는지를 정규식으로 채점한다. LLM judge 없이 결정론적으로 채점하므로 재현 가능하다.

사용법: uv run python scripts/eval_rag_grounding.py
결과: scripts/eval_rag_grounding_results.json 에 원문 응답 전체와 채점 결과 저장.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv()

from flight_alert.services.chatbot_service import ChatbotService  # noqa: E402

RESULTS_PATH = Path(__file__).resolve().parent / "eval_rag_grounding_results.json"

# 각 질문은 실제로 Chroma에 인덱싱된 official_website 문서(airport.kr 크롤링 결과)의
# 위치 정보를 정답(ground truth)으로 사용한다. seed 데이터(음식점 36건)는 크롤링 출처가
# 아니므로 평가셋에서 제외했다.
QUESTIONS: list[dict] = [
    {
        "id": "med_1",
        "title": "인하대학교병원 제1여객터미널 공항의료센터",
        "question": "인천공항 제1여객터미널 안에 있는 인하대학교병원 공항의료센터는 정확히 몇 층 어디에 있어?",
        "expected_floor": "지하1층",
        "expected_keywords": ["지하1층", "동편"],
    },
    {
        "id": "med_2",
        "title": "인천공항 T1 코로나19 검사센터(동)",
        "question": "인천공항 제1터미널 코로나19 검사센터(동쪽)는 어디에 있어?",
        "expected_floor": "1층",
        "expected_keywords": ["교통센터", "1층", "동편"],
    },
    {
        "id": "fin_1",
        "title": "국민은행 환전소(입국장)",
        "question": "인천공항 제1여객터미널 입국장에 있는 국민은행 환전소는 몇 층 어디에 있어?",
        "expected_floor": "1층",
        "expected_keywords": ["1층", "9번 출입구"],
    },
    {
        "id": "fin_2",
        "title": "국민은행 환전소(출국장)",
        "question": "인천공항 제1여객터미널 출국장에 있는 국민은행 환전소는 몇 층 어디에 있어?",
        "expected_floor": "3층",
        "expected_keywords": ["3층", "5번출국장"],
    },
    {
        "id": "fin_3",
        "title": "국민은행 환전소(출국장, 24H)",
        "question": "인천공항 제1여객터미널에서 24시간 운영하는 국민은행 환전소(출국장)는 몇 층 어디에 있어?",
        "expected_floor": "3층",
        "expected_keywords": ["3층", "F 체크인카운터"],
    },
    {
        "id": "tel_1",
        "title": "LG 유플러스 로밍센터(24H)",
        "question": "인천공항 제1여객터미널 LG 유플러스 로밍센터(24시간)는 몇 층 어디에 있어?",
        "expected_floor": "1층",
        "expected_keywords": ["1층", "서편", "F 입국장"],
    },
    {
        "id": "tel_2",
        "title": "KT 로밍센터(24H)",
        "question": "인천공항 제1여객터미널에 24시간 운영하는 KT 로밍센터는 어디에 있어?",
        "expected_floor": "1층",
        "expected_keywords": ["1층", "F 입국장"],
    },
    {
        "id": "lounge_1",
        "title": "캡슐호텔 다락휴(T1)",
        "question": "인천공항 제1여객터미널 캡슐호텔 다락휴는 몇 층 어디에 있어?",
        "expected_floor": "1층",
        "expected_keywords": ["교통센터", "1층", "중앙"],
    },
    {
        "id": "lounge_2",
        "title": "환승호텔(T1)",
        "question": "인천공항 제1여객터미널 환승호텔은 몇 층 어디에 있어?",
        "expected_floor": "4층",
        "expected_keywords": ["4층", "11번 게이트"],
    },
    {
        "id": "admin_1",
        "title": "무인민원발급기(T1, F 체크인)",
        "question": "인천공항 제1여객터미널 F 체크인카운터 근처 무인민원발급기는 몇 층에 있어?",
        "expected_floor": "3층",
        "expected_keywords": ["3층", "F 체크인카운터"],
    },
    {
        "id": "admin_2",
        "title": "여권민원센터(T1)",
        "question": "인천공항 제1여객터미널 여권민원센터는 몇 층 어디에 있어?",
        "expected_floor": "3층",
        "expected_keywords": ["3층", "G 체크인카운터"],
    },
    {
        "id": "info_1",
        "title": "T1 장애인 안심여행센터",
        "question": "인천공항 제1여객터미널 장애인 안심여행센터는 몇 층 어디에 있어?",
        "expected_floor": "3층",
        "expected_keywords": ["3층", "7-8번 출입구"],
    },
    {
        "id": "info_2",
        "title": "환승투어 서비스(T1)",
        "question": "인천공항 제1여객터미널 환승투어 서비스 카운터는 몇 층 어디에 있어?",
        "expected_floor": "1층",
        "expected_keywords": ["1층", "1번 출입구"],
    },
    {
        "id": "postal_1",
        "title": "우편취급국",
        "question": "인천공항 제1여객터미널 우편취급국은 몇 층에 있어?",
        "expected_floor": "2층",
        "expected_keywords": ["2층", "중앙"],
    },
    {
        "id": "postal_2",
        "title": "짐캐리(24H, N 체크인)",
        "question": "인천공항 제1여객터미널 N 체크인카운터 근처 짐캐리(24시간)는 몇 층에 있어?",
        "expected_floor": "3층",
        "expected_keywords": ["3층", "N 체크인카운터"],
    },
    {
        "id": "other_1",
        "title": "롯데렌터카",
        "question": "인천공항 제1여객터미널 롯데렌터카는 몇 층 어디에 있어?",
        "expected_floor": "1층",
        "expected_keywords": ["1층", "13번", "14번"],
    },
    {
        "id": "other_2",
        "title": "크린업에어(T1세탁소)",
        "question": "인천공항 제1여객터미널 세탁소(크린업에어)는 몇 층에 있어?",
        "expected_floor": "지하1층",
        "expected_keywords": ["지하1층", "서편"],
    },
    {
        "id": "fin_4",
        "title": "삼성화재 여행자보험",
        "question": "인천공항 제1여객터미널 삼성화재 여행자보험 창구는 몇 층 어디에 있어?",
        "expected_floor": "3층",
        "expected_keywords": ["3층", "K 체크인카운터"],
    },
]

_FLOOR_RE = re.compile(r"지하\s*\d+\s*층|\d+\s*층")


def _extract_floor_claims(text: str) -> list[str]:
    """응답 텍스트에서 '3층', '지하1층' 같은 층수 언급을 모두 추출(정규화)."""
    found = _FLOOR_RE.findall(text or "")
    return [f.replace(" ", "") for f in found]


def _normalize(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


@dataclass
class GradedAnswer:
    mode: str
    response: str
    matched_keywords: list[str]
    keyword_hit_rate: float  # matched / total expected keywords
    floor_claims: list[str]
    floor_correct: bool | None  # None = 층수를 언급하지 않음(판단 불가)


def _grade(response: str, expected_floor: str, expected_keywords: list[str]) -> GradedAnswer:
    norm_resp = _normalize(response)
    matched = [kw for kw in expected_keywords if _normalize(kw) in norm_resp]
    hit_rate = len(matched) / len(expected_keywords) if expected_keywords else 0.0

    floor_claims = _extract_floor_claims(response)
    exp_floor_norm = _normalize(expected_floor)
    if not floor_claims:
        floor_correct = None
    else:
        floor_correct = any(_normalize(c) == exp_floor_norm for c in floor_claims)

    return GradedAnswer(
        mode="",
        response=response,
        matched_keywords=matched,
        keyword_hit_rate=hit_rate,
        floor_claims=floor_claims,
        floor_correct=floor_correct,
    )


async def _run_one(service: ChatbotService, question: str) -> tuple[str, str]:
    """(mode, response_text) 반환. RAG_ENABLED 환경변수로 legacy/rag 스위칭은 호출부에서 처리."""
    outcome = await service.chat(question, terminal="T1")
    return outcome.mode, outcome.response


async def main() -> None:
    service = ChatbotService()
    results: list[dict] = []

    for q in QUESTIONS:
        print(f"[{q['id']}] {q['title']}", flush=True)

        os.environ["RAG_ENABLED"] = "false"
        legacy_mode, legacy_text = await _run_one(service, q["question"])
        legacy_graded = _grade(legacy_text, q["expected_floor"], q["expected_keywords"])
        legacy_graded.mode = legacy_mode

        os.environ["RAG_ENABLED"] = "true"
        os.environ["RAG_AGENT_ENABLED"] = "false"  # 단순 RAG로 고정(에이전트 도구 호출 배제, 공정 비교)
        rag_mode, rag_text = await _run_one(service, q["question"])
        rag_graded = _grade(rag_text, q["expected_floor"], q["expected_keywords"])
        rag_graded.mode = rag_mode

        results.append(
            {
                "id": q["id"],
                "title": q["title"],
                "question": q["question"],
                "expected_floor": q["expected_floor"],
                "expected_keywords": q["expected_keywords"],
                "legacy": asdict(legacy_graded),
                "rag": asdict(rag_graded),
            }
        )

    def summarize(mode_key: str) -> dict:
        n = len(results)
        avg_hit_rate = sum(r[mode_key]["keyword_hit_rate"] for r in results) / n
        full_match = sum(1 for r in results if r[mode_key]["keyword_hit_rate"] == 1.0)
        floor_stated = [r for r in results if r[mode_key]["floor_correct"] is not None]
        floor_correct = sum(1 for r in floor_stated if r[mode_key]["floor_correct"])
        floor_wrong = len(floor_stated) - floor_correct
        return {
            "n_questions": n,
            "avg_keyword_hit_rate": round(avg_hit_rate, 3),
            "full_keyword_match_count": full_match,
            "floor_claim_stated_count": len(floor_stated),
            "floor_claim_correct_count": floor_correct,
            "floor_claim_wrong_count": floor_wrong,
        }

    summary = {"legacy": summarize("legacy"), "rag": summarize("rag")}

    out = {"summary": summary, "results": results}
    RESULTS_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== 요약 ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\n전체 결과 저장: {RESULTS_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
