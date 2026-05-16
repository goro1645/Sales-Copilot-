from __future__ import annotations

import json
from pathlib import Path
from typing import Any


WORKFLOW_TARGET_BUCKETS = {
    "high_priority_follow_up": 8,
    "standard_follow_up": 8,
    "low_priority_nurture": 7,
    "need_more_info": 7,
}

WORKFLOW_REVIEW_TOOL_NAME = "submit_ai_calibrated_workflow"

_HIGH_PRIORITY_MARKERS = (
    "next week",
    "this week",
    "by friday",
    "approved",
    "proposal",
    "本周",
    "下周",
    "尽快",
    "审批",
    "报价",
)
_NURTURE_MARKERS = (
    "next year",
    "later",
    "reference",
    "material",
    "case study",
    "one-pager",
    "deck",
    "以后",
    "参考",
    "资料",
    "后面",
    "改天",
)
_NEED_MORE_INFO_MARKERS = (
    "unclear",
    "not confirmed",
    "missing",
    "need to confirm",
    "未确认",
    "不清楚",
    "缺",
    "没有",
    "待确认",
)


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _normalize_text(value: Any) -> str:
    return str(value or "").strip().lower()


def load_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_workflow_readme(path: Path, rows: list[dict[str, Any]]) -> None:
    route_counts: dict[str, int] = {}
    for row in rows:
        workflow = row.get("expected_workflow", {})
        route = "unknown"
        if isinstance(workflow, dict):
            route = str(workflow.get("expected_route", "unknown"))
        route_counts[route] = route_counts.get(route, 0) + 1

    lines = [
        "# Workflow-Calibrated 30",
        "",
        "This dataset is an AI-calibrated workflow benchmark draft for Sales Copilot.",
        "",
        "## Included fields",
        "",
        "- `expected_parse`: parse benchmark reference carried over from the source pool",
        "- `expected_workflow.expected_crm_writeback`: canonical CRM writeback expectation",
        "- `expected_workflow.expected_task_bundle`: canonical task generation expectation",
        "- compatibility fields such as `should_write_crm`, `should_generate_tasks`, `required_task_titles`, and `required_risk_flags`",
        "",
        "## Route distribution",
        "",
    ]
    for route, count in sorted(route_counts.items()):
        lines.append(f"- `{route}`: {count}")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def infer_workflow_sampling_bucket(row: dict[str, object]) -> str:
    expected_parse = row.get("expected_parse", {})
    if not isinstance(expected_parse, dict):
        expected_parse = {}

    meeting_note_text = _normalize_text(row.get("meeting_note_text"))
    confirmed_needs = _normalize_string_list(expected_parse.get("confirmed_needs", []))
    budget = _normalize_string_list(expected_parse.get("budget_signals", []))
    timeline = _normalize_string_list(expected_parse.get("timeline_signals", []))
    next_steps = _normalize_string_list(expected_parse.get("next_steps", []))

    if (
        not next_steps
        or any(marker in meeting_note_text for marker in _NEED_MORE_INFO_MARKERS)
        or (confirmed_needs and not budget and not timeline and "confirm" in meeting_note_text)
    ):
        return "need_more_info"
    if budget or timeline or any(marker in meeting_note_text for marker in _HIGH_PRIORITY_MARKERS):
        return "high_priority_follow_up"
    if any(marker in meeting_note_text for marker in _NURTURE_MARKERS):
        return "low_priority_nurture"
    return "standard_follow_up"


def build_workflow_calibrated_sample(
    rows: list[dict[str, object]],
    *,
    target_counts: dict[str, int] | None = None,
) -> list[dict[str, object]]:
    targets = dict(target_counts or WORKFLOW_TARGET_BUCKETS)
    grouped = {bucket: [] for bucket in targets}
    fallback: list[dict[str, object]] = []

    for row in rows:
        copied = dict(row)
        bucket = infer_workflow_sampling_bucket(copied)
        copied["workflow_sampling_bucket"] = bucket
        fallback.append(copied)
        if bucket in grouped:
            grouped[bucket].append(copied)

    selected: list[dict[str, object]] = []
    seen: set[str] = set()
    for bucket, count in targets.items():
        current_count = 0
        for row in grouped[bucket]:
            case_id = str(row.get("case_id", ""))
            if case_id in seen:
                continue
            selected.append(row)
            seen.add(case_id)
            current_count += 1
            if current_count >= count:
                break

    for bucket, count in targets.items():
        current_count = sum(1 for row in selected if row.get("workflow_sampling_bucket") == bucket)
        if current_count >= count:
            continue
        for row in fallback:
            case_id = str(row.get("case_id", ""))
            if case_id in seen:
                continue
            selected.append(row)
            seen.add(case_id)
            current_count += 1
            if current_count >= count:
                break

    return selected


def build_workflow_review_tools() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": WORKFLOW_REVIEW_TOOL_NAME,
                "description": "Return the final AI-calibrated workflow expectation for a Sales Copilot case.",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "expected_workflow": {
                            "type": "object",
                            "properties": {
                                "lead_score_range": {
                                    "type": "array",
                                    "items": {"type": "integer"},
                                    "minItems": 2,
                                    "maxItems": 2,
                                },
                                "lead_priority": {
                                    "type": "string",
                                    "enum": ["low", "medium", "high"],
                                },
                                "opportunity_stage": {
                                    "type": "string",
                                    "enum": [
                                        "discovery",
                                        "qualification",
                                        "proposal",
                                        "negotiation",
                                        "closed_won",
                                        "closed_lost",
                                    ],
                                },
                                "expected_route": {
                                    "type": "string",
                                    "enum": [
                                        "need_more_info",
                                        "low_priority_nurture",
                                        "standard_follow_up",
                                        "high_priority_follow_up",
                                    ],
                                },
                                "expected_crm_writeback": {
                                    "type": "object",
                                    "properties": {
                                        "should_write": {"type": "boolean"},
                                        "account_status": {"type": "string"},
                                        "opportunity_stage": {"type": "string"},
                                        "risk_flags": {"type": "array", "items": {"type": "string"}},
                                        "recommended_next_step": {"type": "string"},
                                        "evidence": {"type": "array", "items": {"type": "string"}},
                                        "acceptable_variants": {"type": "array", "items": {"type": "string"}},
                                    },
                                    "required": [
                                        "should_write",
                                        "account_status",
                                        "opportunity_stage",
                                        "risk_flags",
                                        "recommended_next_step",
                                        "evidence",
                                        "acceptable_variants",
                                    ],
                                    "additionalProperties": False,
                                },
                                "expected_task_bundle": {
                                    "type": "object",
                                    "properties": {
                                        "should_generate": {"type": "boolean"},
                                        "tasks": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "title": {"type": "string"},
                                                    "description": {"type": "string"},
                                                    "priority": {"type": "string"},
                                                    "owner": {"type": "string"},
                                                    "timing_expectation": {"type": "string"},
                                                    "evidence": {"type": "array", "items": {"type": "string"}},
                                                },
                                                "required": [
                                                    "title",
                                                    "description",
                                                    "priority",
                                                    "owner",
                                                    "timing_expectation",
                                                    "evidence",
                                                ],
                                                "additionalProperties": False,
                                            },
                                        },
                                        "acceptable_variants": {"type": "array", "items": {"type": "string"}},
                                    },
                                    "required": ["should_generate", "tasks", "acceptable_variants"],
                                    "additionalProperties": False,
                                },
                            },
                            "required": [
                                "lead_score_range",
                                "lead_priority",
                                "opportunity_stage",
                                "expected_route",
                                "expected_crm_writeback",
                                "expected_task_bundle",
                            ],
                            "additionalProperties": False,
                        },
                        "calibration_note": {"type": "string"},
                    },
                    "required": ["expected_workflow", "calibration_note"],
                    "additionalProperties": False,
                },
            },
        }
    ]


def build_workflow_review_messages(row: dict[str, Any]) -> list[dict[str, str]]:
    expected_parse = row.get("expected_parse", {})
    if not isinstance(expected_parse, dict):
        expected_parse = {}

    lines = [
        f"case_id: {row.get('case_id', '')}",
        f"suggested_route_bucket: {row.get('workflow_sampling_bucket', '')}",
        "",
        "customer_profile_text:",
        str(row.get("customer_profile_text", "")),
        "",
        "meeting_note_text:",
        str(row.get("meeting_note_text", "")),
        "",
        "expected_parse:",
        json.dumps(expected_parse, ensure_ascii=False),
        "",
        "Produce a realistic final workflow expectation focused on CRM writeback quality and task generation quality.",
        "Use concise but actionable evidence and variants. Do not invent unsupported facts.",
    ]
    return [
        {
            "role": "system",
            "content": (
                "You are calibrating a Sales Copilot workflow benchmark draft. "
                "Return the final expected workflow using the tool only. "
                "The goal is to define realistic CRM writeback and task generation expectations, "
                "not to mirror the current system output. "
                "Keep acceptable variants concise. "
                "If the case lacks enough evidence, prefer need_more_info or low_priority_nurture over aggressive follow-up."
            ),
        },
        {"role": "user", "content": "\n".join(lines)},
    ]


def fill_ai_workflow_review_for_row(row: dict[str, Any], *, llm_client: Any) -> dict[str, Any]:
    tool_result = llm_client.complete_with_tool(
        build_workflow_review_messages(row),
        tools=build_workflow_review_tools(),
        tool_choice={"type": "function", "function": {"name": WORKFLOW_REVIEW_TOOL_NAME}},
    )
    tool_name = tool_result.get("tool_name")
    if tool_name != WORKFLOW_REVIEW_TOOL_NAME:
        raise ValueError(f"Unexpected workflow calibration tool call: {tool_name}")

    arguments = tool_result.get("arguments", {})
    if not isinstance(arguments, dict):
        raise ValueError("Workflow calibration arguments must be a dict")

    expected_workflow = arguments.get("expected_workflow", {})
    if not isinstance(expected_workflow, dict):
        raise ValueError("Workflow calibration expected_workflow must be a dict")

    updated = dict(row)
    updated["workflow_review"] = {
        "expected_workflow": expected_workflow,
        "calibration_note": str(arguments.get("calibration_note", "")).strip(),
        "reviewed_by": "ai",
        "review_status": "completed",
    }
    return updated


def fill_ai_workflow_review_rows(rows: list[dict[str, Any]], *, llm_client: Any) -> list[dict[str, Any]]:
    return [fill_ai_workflow_review_for_row(row, llm_client=llm_client) for row in rows]


def export_final_workflow_calibrated_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    final_rows: list[dict[str, Any]] = []
    for row in rows:
        review = row.get("workflow_review", {})
        if not isinstance(review, dict):
            review = {}
        workflow = dict(review.get("expected_workflow", {}))
        if not isinstance(workflow, dict):
            workflow = {}
        crm = workflow.get("expected_crm_writeback", {})
        if not isinstance(crm, dict):
            crm = {}
        task_bundle = workflow.get("expected_task_bundle", {})
        if not isinstance(task_bundle, dict):
            task_bundle = {}
        tasks = task_bundle.get("tasks", [])
        if not isinstance(tasks, list):
            tasks = []

        required_task_titles = [
            str(task.get("title", "")).strip()
            for task in tasks
            if isinstance(task, dict) and str(task.get("title", "")).strip()
        ]

        workflow["should_write_crm"] = bool(crm.get("should_write", False))
        workflow["should_generate_tasks"] = bool(task_bundle.get("should_generate", False))
        workflow["required_task_titles"] = required_task_titles
        workflow["required_risk_flags"] = _normalize_string_list(crm.get("risk_flags", []))

        final_rows.append(
            {
                "case_id": row.get("case_id", ""),
                "segment": row.get("segment", "workflow_calibrated_subset"),
                "source_dataset": row.get("source_dataset", "full-csds-ai-calibrated"),
                "source_case_id": row.get("case_id", ""),
                "meeting_note_text": row.get("meeting_note_text", ""),
                "customer_profile_text": row.get("customer_profile_text", ""),
                "expected_parse": row.get("expected_parse", {}),
                "expected_workflow": workflow,
                "calibration_note": str(review.get("calibration_note", "")).strip(),
            }
        )
    return final_rows
