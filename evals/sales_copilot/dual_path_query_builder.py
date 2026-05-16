"""Build retrieval queries from structured parse payloads.

This file is intentionally simple: it turns workflow parse output into a query
string so we can test retrieval under "real system query" conditions.
"""

from __future__ import annotations

from typing import Any

_QUERY_FIELDS = ("confirmed_needs", "risk_flags", "next_steps", "timeline_signals")


def _normalize_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def build_retrieval_query(parse_payload: dict[str, Any]) -> str:
    # 这里不做复杂 query rewriting，而是直接把结构化字段拼成 query。
    # 这样 dual-path benchmark 才能反映“真实 workflow 自动生成 query”时的检索效果。
    parts: list[str] = []
    seen: set[str] = set()
    for field in _QUERY_FIELDS:
        for item in _normalize_items(parse_payload.get(field, [])):
            if item in seen:
                continue
            seen.add(item)
            parts.append(item)
    return " ".join(parts)
