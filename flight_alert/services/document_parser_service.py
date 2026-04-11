# flight_alert/services/document_parser_service.py
"""HTML/텍스트에서 시설·매장 정보 구조화 (BeautifulSoup + 블록 파싱)"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from bs4 import BeautifulSoup

# 편의시설 탭(공항 사이트 표기)
_FACILITY_TAB_LABELS = frozenset(
    {
        "금융/보험",
        "통신/인터넷",
        "안내데스크",
        "라운지/호텔/휴식",
        "의료/유아",
        "택배/우편",
        "민원행정서비스",
        "기타편의",
    }
)

_TAB_TO_SUBCATEGORY = {
    "금융/보험": "finance",
    "통신/인터넷": "telecom",
    "안내데스크": "information_desk",
    "라운지/호텔/휴식": "lounge_rest",
    "의료/유아": "medical",
    "택배/우편": "postal",
    "민원행정서비스": "admin_service",
    "기타편의": "other",
}

_PHONE_RE = re.compile(r"^(\d{2,4}-\d{3,4}-\d{4}|1\d{3}-\d{4}|\d{4}-\d{4})$")
_HOURS_RE = re.compile(r"\d{1,2}:\d{2}\s*[~∼～]\s*\d{1,2}:\d{2}")


def _slug(s: str, max_len: int = 48) -> str:
    raw = re.sub(r"[^\w가-힣]+", "_", s.strip().lower())
    raw = re.sub(r"_+", "_", raw).strip("_")
    return raw[:max_len] if raw else "doc"


def _infer_terminal(location: str | None) -> str | None:
    if not location:
        return None
    if "제2여객터미널" in location or "제2 터미널" in location:
        return "T2"
    if "제1여객터미널" in location or "제1 터미널" in location:
        return "T1"
    if "탑승동" in location:
        return "CONCOURSE"
    return None


def _infer_zone(location: str | None) -> str | None:
    if not location:
        return None
    if "면세" in location:
        return "면세지역"
    if "환승" in location:
        return "환승지역"
    if "입국" in location:
        return "입국장"
    if "일반" in location:
        return "비면세지역"
    return None


def _infer_floor(location: str | None) -> str | None:
    if not location:
        return None
    m = re.search(r"지하\s*1\s*층|지하1층|B1", location)
    if m:
        return "지하1층"
    m = re.search(r"(\d+)\s*층", location)
    if m:
        return f"{m.group(1)}층"
    return None


def _gate_nearby(location: str | None) -> str | None:
    if not location:
        return None
    m = re.search(r"(\d+)\s*번\s*게이트", location)
    if m:
        return f"{m.group(1)}번 게이트 근처"
    return None


def _make_doc_id(prefix: str, title: str, location: str | None) -> str:
    h = hashlib.md5(f"{title}|{location or ''}".encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{_slug(title, 32)}_{h}"


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    main = (
        soup.select_one("#contents, #content, .contents, main")
        or soup.body
        or soup
    )
    return main.get_text("\n", strip=True)


def parse_facility_html(
    html: str,
    *,
    source_url: str,
    default_terminal: str | None = None,
) -> list[dict[str, Any]]:
    """편의 · 공공시설 HTML → 문서 dict 리스트."""
    text = _html_to_text(html)
    return parse_facility_text(text, source_url=source_url, default_terminal=default_terminal)


def parse_facility_text(
    text: str,
    *,
    source_url: str,
    default_terminal: str | None = None,
) -> list[dict[str, Any]]:
    """본문 텍스트에서 시설 블록 추출 (위치 상세보기 기준 분리)."""
    chunks = re.split(r"위치\s*상세보기", text)
    results: list[dict[str, Any]] = []
    for chunk in chunks:
        chunk = chunk.strip()
        if len(chunk) < 8:
            continue
        lines = [ln.strip() for ln in chunk.splitlines() if ln.strip()]
        if len(lines) < 2:
            continue

        category_kr = None
        title = None
        idx = 0
        if lines[0] in _FACILITY_TAB_LABELS:
            category_kr = lines[0]
            idx = 1
        if idx < len(lines):
            title = lines[idx]
            idx += 1
        if not title:
            continue

        hours: str | None = None
        contact: str | None = None
        location: str | None = None
        extra: list[str] = []

        for line in lines[idx:]:
            if line.startswith("-"):
                body = line.lstrip("-").strip()
                if _HOURS_RE.search(body) or body.startswith("24시간") or "24H" in body:
                    hours = body
                elif _PHONE_RE.match(body.replace(" ", "")):
                    contact = body
                elif "터미널" in body or "층" in body or "게이트" in body or "출입구" in body or "출국장" in body or "입국장" in body:
                    location = body
                else:
                    extra.append(body)
            elif "터미널" in line or "층" in line:
                location = line

        terminal = _infer_terminal(location) or default_terminal
        subcategory = _TAB_TO_SUBCATEGORY.get(category_kr or "", "other")

        content_parts = [
            f"{title}은(는) 인천공항 편의시설입니다.",
            f"운영시간: {hours}" if hours else None,
            f"연락처: {contact}" if contact else None,
            f"위치: {location}" if location else None,
        ]
        content = " ".join(p for p in content_parts if p)

        features: list[str] = []
        if category_kr:
            features.append(category_kr)
        if hours and ("24:00" in hours or "24시간" in hours or "24H" in hours):
            features.append("24시간 운영")
        features.extend(extra[:5])

        doc_id = _make_doc_id("facility", title, location)
        results.append(
            {
                "doc_id": doc_id,
                "title": title[:200],
                "category": "rest",
                "subcategory": subcategory,
                "terminal": terminal,
                "floor": _infer_floor(location),
                "zone": _infer_zone(location),
                "area": None,
                "gate_nearby": _gate_nearby(location),
                "hours": hours,
                "contact": contact,
                "price_range": None,
                "content": content or title,
                "features": features or None,
                "amenities": None,
                "source_url": source_url,
                "source_type": "official_website",
            }
        )
    return results


def parse_food_html(html: str, *, source_url: str) -> list[dict[str, Any]]:
    """식음료 목록 HTML 파싱 (텍스트 블록 휴리스틱)."""
    text = _html_to_text(html)
    return parse_food_text(text, source_url=source_url)


def parse_food_text(text: str, *, source_url: str) -> list[dict[str, Any]]:
    """식음료 페이지: 매장명·층·위주 블록 추출."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    results: list[dict[str, Any]] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if re.search(r"제[12]여객터미널|탑승동", line) and any(
            x in line for x in ("층", "면세", "일반", "게이트", "출국", "식당", "카페", "푸드")
        ):
            location = line
            title = lines[i - 1] if i > 0 else "매장"
            if title in ("식음료", "한식", "양식", "일식", "중식", "카페", "디저트", "패스트푸드"):
                if i + 1 < len(lines):
                    title = lines[i + 1]
            sub = "cafe"
            if any(k in title for k in ("카페", "커피", "베이커리")):
                sub = "cafe"
            elif any(k in title for k in ("맥도날드", "버거", "패스트")):
                sub = "fast_food"
            elif any(k in title for k in ("일식", "초밥", "라멘")):
                sub = "japanese"
            elif any(k in title for k in ("중식", "딤섬")):
                sub = "chinese"
            elif any(k in title for k in ("스테이크", "파스타", "양식")):
                sub = "western"
            elif any(k in title for k in ("한식", "비빔밥", "국밥")):
                sub = "korean_food"

            terminal = _infer_terminal(location)
            doc_id = _make_doc_id("food", title, location)
            content = f"{title} — 위치: {location}"
            results.append(
                {
                    "doc_id": doc_id,
                    "title": title[:200],
                    "category": "food",
                    "subcategory": sub,
                    "terminal": terminal,
                    "floor": _infer_floor(location),
                    "zone": _infer_zone(location),
                    "area": None,
                    "gate_nearby": _gate_nearby(location),
                    "hours": None,
                    "contact": None,
                    "price_range": None,
                    "content": content,
                    "features": ["식음료"],
                    "amenities": None,
                    "source_url": source_url,
                    "source_type": "official_website",
                }
            )
        i += 1
    return results


def build_embedding_text(doc: dict[str, Any]) -> str:
    """임베딩용 문자열."""
    parts = [
        doc.get("title") or "",
        doc.get("content") or "",
        doc.get("category") or "",
        doc.get("subcategory") or "",
        doc.get("terminal") or "",
        doc.get("floor") or "",
        doc.get("zone") or "",
    ]
    feats = doc.get("features") or []
    if isinstance(feats, list):
        parts.append(" ".join(feats))
    return " ".join(p for p in parts if p).strip()
