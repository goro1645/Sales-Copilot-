"""Programmatic task-candidate builder for fact-preserving task generation.

This module sits between parse results and final task generation:
- `build_task_candidates(...)` extracts likely action items from structured facts
- `build_tasks_from_candidates(...)` turns those candidates into task-shaped rows
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any


ACTION_NEED_MARKERS = (
    "proposal",
    "quote",
    "pricing",
    "security",
    "integration",
    "demo",
)
# 只有一部分 confirmed_needs 会进一步转成任务候选。
# 这些 marker 更接近“已经能落成动作”的 need，例如报价、安全材料、集成准备、demo 等。


def _normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        output.append(item)
    return output


def _infer_task_type(text: str) -> str:
    lowered = text.lower()
    if any(token in lowered for token in ("proposal", "quote", "pricing")):
        return "proposal_or_quote"
    if any(token in lowered for token in ("meeting", "demo", "deep-dive", "deep dive", "workshop")):
        return "customer_meeting"
    if any(token in lowered for token in ("security", "integration", "architecture", "materials", "package")):
        return "internal_prep"
    if any(token in lowered for token in ("identify", "clarify", "confirm missing", "stakeholder")):
        return "risk_mitigation"
    return "customer_follow_up"


def _infer_timing_hint(text: str) -> str:
    lowered = text.lower()
    if "today" in lowered:
        return "today"
    if "this week" in lowered or "by friday" in lowered:
        return "this_week"
    if "next week" in lowered:
        return "next_week"
    if "this month" in lowered:
        return "this_month"
    if "this quarter" in lowered:
        return "this_quarter"
    return "unspecified"


def _infer_title(text: str) -> str:
    lowered = text.lower()
    if lowered.startswith("send tailored proposal"):
        return "Send tailored proposal"
    if lowered.startswith("schedule technical deep-dive"):
        return "Schedule technical deep-dive"
    return text[:1].upper() + text[1:] if text else "Follow up"


def build_task_candidates(
    *,
    meeting_summary: dict[str, Any],
    risk_flags: list[str],
    lead_priority: str,
    opportunity_stage: str,
) -> list[dict[str, Any]]:
    # `next_steps` 是最直接的任务候选来源，因为它们已经在回答“接下来要做什么”。
    next_steps = _dedupe(_normalize_list(meeting_summary.get("next_steps")))
    confirmed_needs = _normalize_list(meeting_summary.get("confirmed_needs"))
    candidate_texts = list(next_steps)

    # `confirmed_needs` 只在明显带行动倾向时才升格成候选，避免把所有需求都硬转成任务。
    for need in confirmed_needs:
        lowered = need.lower()
        if any(token in lowered for token in ACTION_NEED_MARKERS):
            candidate_texts.append(need)

    lowered_risks = {flag.lower() for flag in risk_flags}
    # 某些风险标签也会触发补信息任务，例如缺失决策人。
    if "stakeholder_missing" in lowered_risks:
        candidate_texts.append("identify missing decision makers")

    candidate_texts = _dedupe(candidate_texts)
    normalized_priority = lead_priority if lead_priority in {"low", "medium", "high"} else "medium"

    return [
        {
            "text": text,
            "source": "meeting_next_steps" if text in next_steps else "derived_signal",
            "task_type": _infer_task_type(text),
            "priority_hint": normalized_priority,
            "timing_hint": _infer_timing_hint(text),
            "evidence": [text, f"stage={opportunity_stage}"],
        }
        for text in candidate_texts
    ]


def build_tasks_from_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # 这一步仍然是程序整理，不是再起一轮 LLM。
    tasks: list[dict[str, Any]] = []
    for row in candidates:
        text = str(row.get("text", "")).strip()
        if not text:
            continue
        timing_hint = str(row.get("timing_hint", "unspecified")).strip()
        due_in_days = 1 if timing_hint in {"today", "this_week", "unspecified"} else 7
        evidence = "; ".join(str(item).strip() for item in row.get("evidence", []) if str(item).strip())
        tasks.append(
            {
                "title": _infer_title(text),
                "description": evidence or text,
                "priority": str(row.get("priority_hint", "medium")).strip() or "medium",
                "due_at": (date.today() + timedelta(days=due_in_days)).isoformat(),
                "status": "open",
                "owner": "Sales",
            }
        )
    return tasks
