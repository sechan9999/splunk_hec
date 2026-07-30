"""Deterministic classification rules. Agents use these as the authoritative
routing decision (and offline-safe fallback); the LLM only enriches narrative.
Never let a hallucinated label drive assignment — rules decide, LLM explains."""
from __future__ import annotations

# (category, keywords). First match wins; else "other".
CATEGORY_KEYWORDS: list[tuple[str, list[str]]] = [
    ("billing", ["환불", "결제", "청구", "요금", "세금계산서", "refund", "invoice", "billing", "payment", "charge"]),
    ("hardware", ["고장", "파손", "깨졌", "부품", "전원", "작동", "소음", "hardware", "broken", "power", "defect", "부러"]),
    ("software", ["오류", "버그", "앱", "로그인", "업데이트", "화면", "software", "bug", "error", "login", "app", "crash"]),
    ("delivery", ["배송", "택배", "도착", "누락", "지연", "delivery", "shipping", "late", "missing", "tracking"]),
]

HIGH_SEVERITY = ["긴급", "멈춤", "안돼", "불가", "안전", "전체", "다운", "urgent", "critical", "stopped", "safety", "down", "outage"]
LOW_SEVERITY = ["문의", "질문", "사소", "how to", "question", "minor", "inquiry"]

# Which role owns each category (drives assignee selection).
CATEGORY_ROLE = {
    "billing": "accounting",
    "hardware": "production",
    "software": "production",
    "delivery": "as",
    "other": "as",
}


def _contains(text: str, keywords: list[str]) -> bool:
    return any(k in text for k in keywords)


def classify(summary: str) -> tuple[str, str]:
    text = (summary or "").lower()
    category = "other"
    for name, keywords in CATEGORY_KEYWORDS:
        if _contains(text, [k.lower() for k in keywords]):
            category = name
            break
    if _contains(text, [k.lower() for k in HIGH_SEVERITY]):
        severity = "high"
    elif _contains(text, [k.lower() for k in LOW_SEVERITY]):
        severity = "low"
    else:
        severity = "medium"
    return category, severity
