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
_ROUTE_SCORE_BANDS = {
    "low_priority_nurture": (0, 49),
    "standard_follow_up": (50, 79),
    "high_priority_follow_up": (80, 100),
}
_ROUTE_SCORE_BAND_SPILLOVER_LIMIT = 3
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
        "expected_routes": {"standard_follow_up", "high_priority_follow_up"},
        "score_min": 49,
        "score_max": 100,
    },
    "medium_intent_nurture": {
        "allowed_combinations": (
            {
                "lead_priority": "low",
                "expected_route": "low_priority_nurture",
                "score_min": 35,
                "score_max": 49,
            },
            {
                "lead_priority": "medium",
                "expected_route": "standard_follow_up",
                "score_min": 50,
                "score_max": 79,
            },
        ),
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


def _score_range_overlaps_route(score_range: list[int], route: str) -> bool:
    if route == "need_more_info":
        return True
    route_band = _ROUTE_SCORE_BANDS.get(route)
    if route_band is None:
        return False
    score_min, score_max = score_range
    route_min, route_max = route_band
    if score_max < route_min or score_min > route_max:
        return False

    spillover_below = max(0, route_min - score_min) if score_min < route_min else 0
    spillover_above = max(0, score_max - route_max) if score_max > route_max else 0
    return spillover_below + spillover_above <= _ROUTE_SCORE_BAND_SPILLOVER_LIMIT


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

    allowed_combinations = contract.get("allowed_combinations")
    if allowed_combinations is None:
        if lead_priority != contract["lead_priority"]:
            raise ValueError(f"{label} lead_priority must be {contract['lead_priority']}")
        if lead_score_range[0] < contract["score_min"] or lead_score_range[1] > contract["score_max"]:
            raise ValueError(
                f"{label} lead_score_range must stay within {contract['score_min']}..{contract['score_max']}"
            )
        allowed_routes = contract.get("expected_routes")
        if allowed_routes is not None:
            allowed_routes_set = set(allowed_routes)
            if expected_route != "need_more_info" and expected_route not in allowed_routes_set:
                raise ValueError(
                    f"{label} expected_route must be one of {sorted(allowed_routes_set)}"
                )
        elif expected_route != contract["expected_route"] and expected_route != "need_more_info":
            raise ValueError(f"{label} expected_route must be {contract['expected_route']}")
        if not _score_range_overlaps_route(lead_score_range, expected_route):
            route_band = _ROUTE_SCORE_BANDS[expected_route]
            raise ValueError(
                f"{label} lead_score_range must overlap with {expected_route} "
                f"({route_band[0]}..{route_band[1]})"
            )
    else:
        matched_combination = None
        for combination in allowed_combinations:
            if (
                lead_priority == combination["lead_priority"]
                and expected_route == combination["expected_route"]
            ):
                matched_combination = combination
                break
        if matched_combination is None:
            raise ValueError(
                f"{label} must use one of the allowed lead_priority/expected_route combinations"
            )
        if (
            lead_score_range[0] < matched_combination["score_min"]
            or lead_score_range[1] > matched_combination["score_max"]
        ):
            raise ValueError(
                f"{label} lead_score_range must stay within "
                f"{matched_combination['score_min']}..{matched_combination['score_max']}"
            )
        if not _score_range_overlaps_route(lead_score_range, expected_route):
            route_band = _ROUTE_SCORE_BANDS[expected_route]
            raise ValueError(
                f"{label} lead_score_range must overlap with {expected_route} "
                f"({route_band[0]}..{route_band[1]})"
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
