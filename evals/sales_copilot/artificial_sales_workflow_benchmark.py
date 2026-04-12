from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evals.sales_copilot.workflow_calibrated_benchmark import write_jsonl


ARTIFICIAL_ROUTE_TARGETS = {
    "high_priority_follow_up": 15,
    "standard_follow_up": 15,
    "need_more_info": 10,
    "low_priority_nurture": 10,
}

ARTIFICIAL_PHASE_TARGETS = {
    "initial_contact": 10,
    "discovery_qualification": 10,
    "evaluation_objection": 10,
    "commercial_progression": 10,
    "nurture_deferred": 10,
}

ARTIFICIAL_SALES_TOOL_NAME = "submit_artificial_sales_workflow_case"

_SOURCE_CASE_TYPES = (
    "merchant_onboarding",
    "crm_integration",
    "private_deployment",
    "team_collaboration",
    "reporting_analytics",
    "campaign_operations",
    "budget_pushback",
    "implementation_effort",
    "security_review",
    "stalled_follow_up",
)


def build_sales_case_blueprints() -> list[dict[str, str]]:
    route_slots = (
        ["high_priority_follow_up"] * ARTIFICIAL_ROUTE_TARGETS["high_priority_follow_up"]
        + ["standard_follow_up"] * ARTIFICIAL_ROUTE_TARGETS["standard_follow_up"]
        + ["need_more_info"] * ARTIFICIAL_ROUTE_TARGETS["need_more_info"]
        + ["low_priority_nurture"] * ARTIFICIAL_ROUTE_TARGETS["low_priority_nurture"]
    )
    phase_slots = (
        ["initial_contact"] * ARTIFICIAL_PHASE_TARGETS["initial_contact"]
        + ["discovery_qualification"] * ARTIFICIAL_PHASE_TARGETS["discovery_qualification"]
        + ["evaluation_objection"] * ARTIFICIAL_PHASE_TARGETS["evaluation_objection"]
        + ["commercial_progression"] * ARTIFICIAL_PHASE_TARGETS["commercial_progression"]
        + ["nurture_deferred"] * ARTIFICIAL_PHASE_TARGETS["nurture_deferred"]
    )
    blueprints: list[dict[str, str]] = []
    for index in range(50):
        blueprints.append(
            {
                "case_id": f"artificial_sales_{index + 1:03d}",
                "segment": "artificial_sales_workflow_benchmark",
                "target_route": route_slots[index],
                "funnel_phase": phase_slots[index],
                "source_case_type": _SOURCE_CASE_TYPES[index % len(_SOURCE_CASE_TYPES)],
            }
        )
    return blueprints


def _require_dict(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a dict")
    return value


def validate_authored_case(row: dict[str, Any]) -> None:
    for field in (
        "case_id",
        "segment",
        "source_case_type",
        "funnel_phase",
        "target_route",
        "customer_profile_text",
        "meeting_note_text",
        "expected_parse",
        "expected_workflow",
        "author_note",
    ):
        if field not in row:
            raise ValueError(f"Missing required field: {field}")

    expected_parse = _require_dict(row["expected_parse"], "expected_parse")
    for field in (
        "account_name",
        "customer_roles",
        "confirmed_needs",
        "objections",
        "next_steps",
        "budget_signals",
        "timeline_signals",
        "competitors",
    ):
        if field not in expected_parse:
            raise ValueError(f"Missing expected_parse field: {field}")

    workflow = _require_dict(row["expected_workflow"], "expected_workflow")
    for field in (
        "lead_score_range",
        "lead_priority",
        "opportunity_stage",
        "expected_route",
        "expected_crm_writeback",
        "expected_task_bundle",
    ):
        if field not in workflow:
            raise ValueError(f"Missing expected_workflow field: {field}")

    crm = _require_dict(workflow["expected_crm_writeback"], "expected_workflow.expected_crm_writeback")
    for field in (
        "should_write",
        "account_status",
        "opportunity_stage",
        "risk_flags",
        "recommended_next_step",
        "evidence",
        "acceptable_variants",
    ):
        if field not in crm:
            raise ValueError(f"Missing expected_crm_writeback field: {field}")

    task_bundle = _require_dict(workflow["expected_task_bundle"], "expected_workflow.expected_task_bundle")
    for field in ("should_generate", "tasks", "acceptable_variants"):
        if field not in task_bundle:
            raise ValueError(f"Missing expected_task_bundle field: {field}")

    target_route = str(row.get("target_route", "")).strip()
    expected_route = str(workflow.get("expected_route", "")).strip()
    if target_route and expected_route != target_route:
        raise ValueError(
            f"expected_route must match target_route: expected_route={expected_route!r}, target_route={target_route!r}"
        )


def write_artificial_sales_readme(path: Path, rows: list[dict[str, Any]]) -> None:
    route_counts: dict[str, int] = {}
    phase_counts: dict[str, int] = {}
    for row in rows:
        workflow = row.get("expected_workflow", {})
        if isinstance(workflow, dict):
            route = str(workflow.get("expected_route", "unknown"))
            route_counts[route] = route_counts.get(route, 0) + 1
        phase = str(row.get("funnel_phase", "unknown"))
        phase_counts[phase] = phase_counts.get(phase, 0) + 1

    lines = [
        "# Artificial Sales Workflow Benchmark 50",
        "",
        "AI-authored ecommerce merchant/platform sales workflow benchmark draft.",
        "",
        "## Route distribution",
        "",
    ]
    for route, count in sorted(route_counts.items()):
        lines.append(f"- `{route}`: {count}")
    lines.extend(["", "## Funnel distribution", ""])
    for phase, count in sorted(phase_counts.items()):
        lines.append(f"- `{phase}`: {count}")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_artificial_sales_tools() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": ARTIFICIAL_SALES_TOOL_NAME,
                "description": "Return one authored ecommerce merchant/platform sales workflow benchmark case.",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_profile_text": {"type": "string"},
                        "meeting_note_text": {"type": "string"},
                        "expected_parse": {
                            "type": "object",
                            "properties": {
                                "account_name": {"type": "string"},
                                "customer_roles": {"type": "array", "items": {"type": "string"}},
                                "confirmed_needs": {"type": "array", "items": {"type": "string"}},
                                "objections": {"type": "array", "items": {"type": "string"}},
                                "next_steps": {"type": "array", "items": {"type": "string"}},
                                "budget_signals": {"type": "array", "items": {"type": "string"}},
                                "timeline_signals": {"type": "array", "items": {"type": "string"}},
                                "competitors": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": [
                                "account_name",
                                "customer_roles",
                                "confirmed_needs",
                                "objections",
                                "next_steps",
                                "budget_signals",
                                "timeline_signals",
                                "competitors",
                            ],
                            "additionalProperties": False,
                        },
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
                        "author_note": {"type": "string"},
                    },
                    "required": [
                        "customer_profile_text",
                        "meeting_note_text",
                        "expected_parse",
                        "expected_workflow",
                        "author_note",
                    ],
                    "additionalProperties": False,
                },
            },
        }
    ]


def build_artificial_sales_messages(blueprint: dict[str, str]) -> list[dict[str, str]]:
    guidance = {
        "knowledge_assumption": "Mix product capability, merchant/platform rules, and sales playbook knowledge.",
        "style": "Use a meeting-note-first style with light dialogue feel, not polished benchmark prose.",
        "authoring_rules": [
            "Keep the scenario plausible for ecommerce merchant/platform sales.",
            "Align expected_route with target_route exactly.",
            "Make CRM and tasks actionable rather than generic.",
            "Do not invent facts not supported by the authored note.",
        ],
        "blueprint": blueprint,
    }
    return [
        {
            "role": "system",
            "content": (
                "You are authoring one ecommerce merchant/platform sales workflow benchmark case. "
                "Return the final case using the tool only. "
                "The case should be realistic, sales-oriented, and suitable for route, CRM, task, and RAG evaluation."
            ),
        },
        {"role": "user", "content": json.dumps(guidance, ensure_ascii=False)},
    ]


def author_sales_case(blueprint: dict[str, str], *, llm_client: Any) -> dict[str, Any]:
    tool_result = llm_client.complete_with_tool(
        build_artificial_sales_messages(blueprint),
        tools=build_artificial_sales_tools(),
        tool_choice={"type": "function", "function": {"name": ARTIFICIAL_SALES_TOOL_NAME}},
    )
    if tool_result.get("tool_name") != ARTIFICIAL_SALES_TOOL_NAME:
        raise ValueError(f"Unexpected artificial sales tool call: {tool_result.get('tool_name')}")

    arguments = tool_result.get("arguments", {})
    if not isinstance(arguments, dict):
        raise ValueError("Artificial sales case arguments must be a dict")

    row = dict(blueprint)
    row.update(arguments)
    validate_authored_case(row)
    return row


def author_sales_cases(
    blueprints: list[dict[str, str]],
    *,
    llm_client: Any,
) -> list[dict[str, Any]]:
    return [author_sales_case(blueprint, llm_client=llm_client) for blueprint in blueprints]
