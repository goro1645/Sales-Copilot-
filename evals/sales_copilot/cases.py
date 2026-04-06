from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TypedDict, cast


class ExpectedParse(TypedDict):
    account_name: str
    customer_roles: list[str]
    confirmed_needs: list[str]
    budget_signals: list[str]
    timeline_signals: list[str]
    next_steps: list[str]
    competitors: list[str]


class ExpectedWorkflow(TypedDict):
    lead_score_range: list[int]
    lead_priority: str
    opportunity_stage: str
    expected_route: str
    should_write_crm: bool
    should_generate_tasks: bool
    required_task_titles: list[str]
    required_risk_flags: list[str]


class GoldenCase(TypedDict):
    case_id: str
    segment: str
    customer_profile_text: str
    meeting_note_text: str
    expected_parse: ExpectedParse
    expected_workflow: ExpectedWorkflow


_TOP_LEVEL_FIELDS = (
    "case_id",
    "segment",
    "customer_profile_text",
    "meeting_note_text",
    "expected_parse",
    "expected_workflow",
)
_EXPECTED_PARSE_FIELDS = (
    "account_name",
    "customer_roles",
    "confirmed_needs",
    "budget_signals",
    "timeline_signals",
    "next_steps",
    "competitors",
)
_EXPECTED_WORKFLOW_FIELDS = (
    "lead_score_range",
    "lead_priority",
    "opportunity_stage",
    "expected_route",
    "should_write_crm",
    "should_generate_tasks",
    "required_task_titles",
    "required_risk_flags",
)
_ALLOWED_SEGMENTS = {
    "high_intent_complete",
    "high_intent_missing_facts",
    "medium_intent_nurture",
    "low_intent_or_noise",
}
_ALLOWED_EXPECTED_ROUTES = {
    "need_more_info",
    "low_priority_nurture",
    "standard_follow_up",
    "high_priority_follow_up",
}
_ALLOWED_OPPORTUNITY_STAGES = {
    "discovery",
    "qualification",
    "proposal",
    "negotiation",
    "closed_won",
    "closed_lost",
}
_ALLOWED_LEAD_PRIORITIES = {"low", "medium", "high"}
_STABLE_RISK_FLAG_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_DETERMINISTIC_MISSING_FACTS_TASK_TITLES = {
    "Confirm budget range",
    "Confirm decision timeline",
    "Identify decision makers",
    "Schedule qualification follow-up",
    "Clarify qualification gaps",
}
_SEGMENT_CONTRACTS = {
    "high_intent_complete": {
        "lead_priority": "high",
        "expected_route": "high_priority_follow_up",
        "score_min": 78,
        "score_max": 100,
    },
    "high_intent_missing_facts": {
        "lead_priority": "high",
        "expected_route": "high_priority_follow_up",
        "score_min": 62,
        "score_max": 100,
    },
    "medium_intent_nurture": {
        "lead_priority": "medium",
        "expected_route": "standard_follow_up",
        "score_min": 50,
        "score_max": 79,
    },
    "low_intent_or_noise": {
        "lead_priority": "low",
        "expected_route": "low_priority_nurture",
        "score_min": 0,
        "score_max": 49,
    },
}


def _missing_fields(data: dict[str, object], required_fields: tuple[str, ...]) -> list[str]:
    return [field for field in required_fields if field not in data]


def _ensure_object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _validate_fields(
    data: dict[str, object],
    required_fields: tuple[str, ...],
    label: str,
    error_label: str,
) -> None:
    missing_fields = _missing_fields(data, required_fields)
    if missing_fields:
        raise ValueError(f"{label} missing {error_label}: {', '.join(missing_fields)}")


def _ensure_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def _ensure_bool(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be a boolean")
    return value


def _ensure_string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list of strings")
    result: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{label}[{index}] must be a non-empty string")
        result.append(item.strip())
    return result


def _ensure_stable_risk_flags(value: object, label: str) -> list[str]:
    flags = _ensure_string_list(value, label)
    for index, flag in enumerate(flags):
        if not _STABLE_RISK_FLAG_PATTERN.fullmatch(flag):
            raise ValueError(f"{label}[{index}] must use snake_case stable tags")
    return flags


def _ensure_lead_score_range(value: object, label: str) -> list[int]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{label} must be a list of exactly 2 integers")
    normalized: list[int] = []
    for index, item in enumerate(value):
        if not isinstance(item, int) or isinstance(item, bool):
            raise ValueError(f"{label}[{index}] must be an integer")
        if item < 0 or item > 100:
            raise ValueError(f"{label}[{index}] must be between 0 and 100")
        normalized.append(item)
    if normalized[0] > normalized[1]:
        raise ValueError(f"{label} must be in ascending order")
    return normalized


def _ensure_segment(value: object, label: str) -> str:
    segment = _ensure_string(value, label)
    if segment not in _ALLOWED_SEGMENTS:
        raise ValueError(f"{label} must be one of {sorted(_ALLOWED_SEGMENTS)}")
    return segment


def _ensure_opportunity_stage(value: object, label: str) -> str:
    stage = _ensure_string(value, label)
    if stage not in _ALLOWED_OPPORTUNITY_STAGES:
        raise ValueError(f"{label} must be one of {sorted(_ALLOWED_OPPORTUNITY_STAGES)}")
    return stage


def _validate_segment_contract(
    *,
    segment: str,
    lead_priority: str,
    expected_route: str,
    lead_score_range: list[int],
    required_risk_flags: list[str],
    should_generate_tasks: bool,
    required_task_titles: list[str],
    label: str,
) -> None:
    contract = _SEGMENT_CONTRACTS.get(segment)
    if contract is None:
        raise ValueError(f"{label} must be one of {sorted(_SEGMENT_CONTRACTS)}")

    if lead_priority != contract["lead_priority"]:
        raise ValueError(f"{label} lead_priority must be {contract['lead_priority']}")
    if segment == "high_intent_missing_facts":
        if expected_route not in {"high_priority_follow_up", "standard_follow_up", "need_more_info"}:
            raise ValueError(
                f"{label} expected_route must be standard_follow_up or high_priority_follow_up"
            )
    elif expected_route != contract["expected_route"] and expected_route != "need_more_info":
        raise ValueError(f"{label} expected_route must be {contract['expected_route']}")
    if lead_score_range[0] < contract["score_min"] or lead_score_range[1] > contract["score_max"]:
        raise ValueError(
            f"{label} lead_score_range must stay within {contract['score_min']}..{contract['score_max']}"
        )
    if segment == "high_intent_missing_facts" and "missing_required_facts" not in required_risk_flags:
        raise ValueError(f"{label} missing_required_facts must be present for this segment")
    if segment != "high_intent_missing_facts" and "missing_required_facts" in required_risk_flags:
        raise ValueError(f"{label} missing_required_facts is only allowed for high_intent_missing_facts")
    if "missing_required_facts" in required_risk_flags and (
        not should_generate_tasks or not required_task_titles
    ):
        raise ValueError(
            f"{label} required_missing_required_facts_tasks must be enabled and have task titles"
        )


def _validate_task_titles(
    *,
    required_task_titles: list[str],
    next_steps: list[str],
    required_risk_flags: list[str],
    label: str,
) -> None:
    for title in required_task_titles:
        if title in next_steps:
            continue
        if title in _DETERMINISTIC_MISSING_FACTS_TASK_TITLES and "missing_required_facts" in required_risk_flags:
            continue
        raise ValueError(
            f"{label} required_task_titles must come from expected_parse.next_steps or deterministic missing-facts tasks"
        )


def load_golden_cases(path: str | Path) -> list[GoldenCase]:
    cases: list[GoldenCase] = []
    seen_case_ids: set[str] = set()
    file_path = Path(path)

    with file_path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue

            record = json.loads(line)
            top_level = _ensure_object(record, f"line {line_number}")
            _validate_fields(
                top_level,
                _TOP_LEVEL_FIELDS,
                f"line {line_number}",
                "required_top_level_fields",
            )

            case_id = _ensure_string(top_level["case_id"], f"line {line_number} case_id")
            if case_id in seen_case_ids:
                raise ValueError(f"line {line_number} case_id must be unique: {case_id}")
            seen_case_ids.add(case_id)

            segment = _ensure_segment(top_level["segment"], f"line {line_number} segment")
            customer_profile_text = _ensure_string(top_level["customer_profile_text"], f"line {line_number} customer_profile_text")
            meeting_note_text = _ensure_string(top_level["meeting_note_text"], f"line {line_number} meeting_note_text")

            expected_parse_raw = _ensure_object(top_level["expected_parse"], f"line {line_number} expected_parse")
            _validate_fields(
                expected_parse_raw,
                _EXPECTED_PARSE_FIELDS,
                f"line {line_number} expected_parse",
                "required_parse_fields",
            )
            expected_parse = {
                "account_name": _ensure_string(expected_parse_raw["account_name"], f"line {line_number} expected_parse.account_name"),
                "customer_roles": _ensure_string_list(expected_parse_raw["customer_roles"], f"line {line_number} expected_parse.customer_roles"),
                "confirmed_needs": _ensure_string_list(expected_parse_raw["confirmed_needs"], f"line {line_number} expected_parse.confirmed_needs"),
                "budget_signals": _ensure_string_list(expected_parse_raw["budget_signals"], f"line {line_number} expected_parse.budget_signals"),
                "timeline_signals": _ensure_string_list(expected_parse_raw["timeline_signals"], f"line {line_number} expected_parse.timeline_signals"),
                "next_steps": _ensure_string_list(expected_parse_raw["next_steps"], f"line {line_number} expected_parse.next_steps"),
                "competitors": _ensure_string_list(expected_parse_raw["competitors"], f"line {line_number} expected_parse.competitors"),
            }

            expected_workflow_raw = _ensure_object(
                top_level["expected_workflow"],
                f"line {line_number} expected_workflow",
            )
            _validate_fields(
                expected_workflow_raw,
                _EXPECTED_WORKFLOW_FIELDS,
                f"line {line_number} expected_workflow",
                "required_workflow_fields",
            )
            lead_score_range = _ensure_lead_score_range(
                expected_workflow_raw["lead_score_range"],
                f"line {line_number} expected_workflow.lead_score_range",
            )
            expected_route = _ensure_string(
                expected_workflow_raw["expected_route"],
                f"line {line_number} expected_workflow.expected_route",
            )
            if expected_route not in _ALLOWED_EXPECTED_ROUTES:
                raise ValueError(
                    f"line {line_number} expected_workflow.expected_route must be one of "
                    f"{sorted(_ALLOWED_EXPECTED_ROUTES)}"
                )

            lead_priority = _ensure_string(
                expected_workflow_raw["lead_priority"],
                f"line {line_number} expected_workflow.lead_priority",
            )
            if lead_priority not in _ALLOWED_LEAD_PRIORITIES:
                raise ValueError(
                    f"line {line_number} expected_workflow.lead_priority must be one of "
                    f"{sorted(_ALLOWED_LEAD_PRIORITIES)}"
                )

            should_generate_tasks = _ensure_bool(
                expected_workflow_raw["should_generate_tasks"],
                f"line {line_number} expected_workflow.should_generate_tasks",
            )
            required_task_titles = _ensure_string_list(
                expected_workflow_raw["required_task_titles"],
                f"line {line_number} expected_workflow.required_task_titles",
            )
            if not should_generate_tasks and required_task_titles:
                raise ValueError(
                    f"line {line_number} expected_workflow.required_task_titles must be empty when "
                    "should_generate_tasks is false"
                )
            if should_generate_tasks and not required_task_titles:
                raise ValueError(
                    f"line {line_number} expected_workflow.required_task_titles must not be empty when "
                    "should_generate_tasks is true"
                )
            required_risk_flags = _ensure_stable_risk_flags(
                expected_workflow_raw["required_risk_flags"],
                f"line {line_number} expected_workflow.required_risk_flags",
            )

            expected_workflow = {
                "lead_score_range": lead_score_range,
                "lead_priority": lead_priority,
                "opportunity_stage": _ensure_opportunity_stage(
                    expected_workflow_raw["opportunity_stage"],
                    f"line {line_number} expected_workflow.opportunity_stage",
                ),
                "expected_route": expected_route,
                "should_write_crm": _ensure_bool(
                    expected_workflow_raw["should_write_crm"],
                    f"line {line_number} expected_workflow.should_write_crm",
                ),
                "should_generate_tasks": should_generate_tasks,
                "required_task_titles": required_task_titles,
                "required_risk_flags": required_risk_flags,
            }

            _validate_segment_contract(
                segment=segment,
                lead_priority=expected_workflow["lead_priority"],
                expected_route=expected_workflow["expected_route"],
                lead_score_range=expected_workflow["lead_score_range"],
                required_risk_flags=expected_workflow["required_risk_flags"],
                should_generate_tasks=expected_workflow["should_generate_tasks"],
                required_task_titles=expected_workflow["required_task_titles"],
                label=f"line {line_number} segment",
            )
            _validate_task_titles(
                required_task_titles=expected_workflow["required_task_titles"],
                next_steps=expected_parse["next_steps"],
                required_risk_flags=expected_workflow["required_risk_flags"],
                label=f"line {line_number} expected_workflow",
            )

            cases.append(
                cast(
                    GoldenCase,
                    {
                        "case_id": case_id,
                        "segment": segment,
                        "customer_profile_text": customer_profile_text,
                        "meeting_note_text": meeting_note_text,
                        "expected_parse": cast(ExpectedParse, expected_parse),
                        "expected_workflow": cast(ExpectedWorkflow, expected_workflow),
                    },
                )
            )

    return cases
