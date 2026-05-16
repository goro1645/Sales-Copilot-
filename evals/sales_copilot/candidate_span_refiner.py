from __future__ import annotations

from typing import Any

from sales_copilot.prompts import build_signal_candidate_generation_messages

_CANDIDATE_TOOL_NAME = "propose_signal_candidates"
_ALLOWED_LABELS = ("budget_signals", "timeline_signals", "next_steps", "other")
_BUDGET_MARKERS = (
    "退款",
    "补偿",
    "优惠券",
    "差价",
    "返还",
    "价格",
    "费用",
    "发票",
    "refund",
    "coupon",
    "discount",
    "price",
    "compensation",
    "invoice",
    "fee",
)
_TIME_MARKERS = (
    "今天",
    "明天",
    "之后",
    "完成后",
    "订单完成后",
    "工作日内",
    "within",
    "after",
    "tomorrow",
    "today",
)
_ACTION_MARKERS = (
    "联系",
    "申请",
    "修改",
    "留下信息",
    "重新下单",
    "寄回",
    "回电",
    "处理",
    "帮助",
    "回复",
    "provide",
    "contact",
    "apply",
    "modify",
    "reorder",
    "leave",
    "help",
    "reply",
    "process",
)


def _count_hits(text: str, markers: tuple[str, ...]) -> int:
    lowered = text.lower()
    hits = 0
    for marker in markers:
        if marker.isascii():
            hits += int(marker in lowered)
        else:
            hits += int(marker in text)
    return hits


def _detect_semantics(text: str) -> dict[str, int]:
    return {
        "budget": _count_hits(text, _BUDGET_MARKERS),
        "timeline": _count_hits(text, _TIME_MARKERS),
        "action": _count_hits(text, _ACTION_MARKERS),
    }


def _build_candidate_tool_schema() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": _CANDIDATE_TOOL_NAME,
            "description": "Propose multiple candidate spans copied verbatim from the meeting note text.",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "candidates": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "candidate_id": {"type": "string"},
                                "text": {"type": "string"},
                                "coarse_label": {
                                    "type": "string",
                                    "enum": list(_ALLOWED_LABELS),
                                },
                            },
                            "required": ["candidate_id", "text", "coarse_label"],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["candidates"],
                "additionalProperties": False,
            },
        },
    }


def generate_signal_candidates(
    *,
    meeting_note_text: str,
    parse_result: dict[str, Any],
    llm_client,
    max_candidates: int = 8,
) -> list[dict[str, str]]:
    messages = build_signal_candidate_generation_messages(
        meeting_note_text=meeting_note_text,
        baseline_parse=parse_result,
    )
    tool_result = llm_client.complete_with_tool(
        messages,
        tools=[_build_candidate_tool_schema()],
        tool_choice={"type": "function", "function": {"name": _CANDIDATE_TOOL_NAME}},
    )
    if tool_result.get("tool_name") != _CANDIDATE_TOOL_NAME:
        raise ValueError("candidate generation returned an unexpected tool")
    payload = tool_result.get("arguments")
    if not isinstance(payload, dict):
        raise ValueError("candidate generation tool arguments must be a JSON object")
    rows = payload.get("candidates")
    if not isinstance(rows, list):
        raise ValueError("candidate generation tool arguments are missing candidates")

    normalized: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        candidate_id = str(row.get("candidate_id", "")).strip()
        text = str(row.get("text", "")).strip()
        coarse_label = str(row.get("coarse_label", "")).strip()
        if not candidate_id or not text or coarse_label not in _ALLOWED_LABELS:
            continue
        if text not in meeting_note_text:
            continue
        normalized.append(
            {
                "candidate_id": candidate_id,
                "text": text,
                "coarse_label": coarse_label,
            }
        )
        if len(normalized) >= max_candidates:
            break
    return normalized


def score_candidate(candidate: dict[str, str]) -> float:
    text = candidate["text"]
    coarse_label = candidate["coarse_label"]
    semantics = _detect_semantics(text)
    score = 0.20

    if coarse_label == "timeline_signals" and semantics["timeline"] > 0:
        score += 0.40
    elif coarse_label == "budget_signals" and semantics["budget"] > 0:
        score += 0.40
    elif coarse_label == "next_steps" and semantics["action"] > 0:
        score += 0.35

    active = sum(1 for value in semantics.values() if value > 0)
    if active == 1:
        score += 0.20
    elif active == 2:
        score += 0.05

    length = len(text.strip())
    if length <= 12:
        score += 0.15
    elif length <= 24:
        score += 0.08
    elif length >= 32:
        score -= 0.10

    if coarse_label == "timeline_signals" and semantics["action"] > 0:
        score -= 0.15
    if coarse_label == "budget_signals" and semantics["action"] > 0:
        score -= 0.10

    return score


def _dedupe_candidates(candidates: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, str]] = []
    for row in candidates:
        key = (row["coarse_label"], row["text"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def select_field_candidates(
    candidates: list[dict[str, str]],
    *,
    field: str,
    top_k: int,
) -> list[str]:
    eligible = [row for row in _dedupe_candidates(candidates) if row["coarse_label"] == field]
    ranked = sorted(
        eligible,
        key=lambda row: (-score_candidate(row), len(row["text"]), row["candidate_id"]),
    )
    return [row["text"] for row in ranked[:top_k]]


def refine_parse_result_with_candidates(
    parse_result: dict[str, Any],
    *,
    meeting_note_text: str,
    llm_client,
) -> dict[str, Any]:
    refined = dict(parse_result)
    for field in ("budget_signals", "timeline_signals", "next_steps"):
        existing = refined.get(field, [])
        refined[field] = list(existing) if isinstance(existing, list) else []

    candidates = generate_signal_candidates(
        meeting_note_text=meeting_note_text,
        parse_result=parse_result,
        llm_client=llm_client,
    )

    for field, top_k in (("budget_signals", 2), ("timeline_signals", 2)):
        for text in select_field_candidates(candidates, field=field, top_k=top_k):
            if text not in refined[field]:
                refined[field].append(text)

    return refined
