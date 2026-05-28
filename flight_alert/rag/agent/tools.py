# flight_alert/rag/agent/tools.py
"""OpenAI Chat Completions용 function tools 스키마."""

from typing import Any

# gpt-4o-mini 호환: type: function + function.{name,description,parameters}


def openai_tool_specs() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "search_airport_docs",
                "description": (
                    "인천공항 안내 문서를 의미(임베딩) 검색합니다. "
                    "시설·식음료·절차 등 질문에 가장 먼저 사용하세요. "
                    "결과가 부족하면 relax_terminal=true로 재검색할 수 있습니다."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "검색 질의(한국어 키워드 문장)",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "반환할 최대 문서 수",
                            "default": 6,
                        },
                        "category": {
                            "type": "string",
                            "description": (
                                "선택. rest|food|shopping|transport|procedure 중 하나, "
                                "모르면 생략"
                            ),
                        },
                        "terminal": {
                            "type": "string",
                            "description": "선택. T1 또는 T2. 생략 시 사용자 기본 터미널 적용",
                        },
                        "relax_terminal": {
                            "type": "boolean",
                            "description": "true면 터미널 조건 없이 전체에서 검색",
                            "default": False,
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_airport_docs_keyword",
                "description": (
                    "제목·본문 부분 문자열 일치로 검색합니다. "
                    "고유 명칭·전화번호·층 정보 등 키워드가 뚜렷할 때 보조로 사용하세요."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "top_k": {"type": "integer", "default": 8},
                        "category": {"type": "string"},
                        "terminal": {"type": "string"},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_airport_doc_categories",
                "description": "DB에 있는 문서 category 값 목록을 반환합니다.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_airport_document",
                "description": "doc_id로 문서 한 건을 정확히 가져옵니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "doc_id": {"type": "string"},
                    },
                    "required": ["doc_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_airport_docs_hybrid",
                "description": (
                    "벡터 유사도와 키워드 일치를 결합한 하이브리드 검색입니다. "
                    "벡터 검색 결과가 불충분하거나 특정 명칭이 포함된 복합 질문에 사용하세요."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "검색 질의",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "반환할 최대 문서 수",
                            "default": 6,
                        },
                        "category": {"type": "string"},
                        "terminal": {"type": "string"},
                    },
                    "required": ["query"],
                },
            },
        },
    ]
