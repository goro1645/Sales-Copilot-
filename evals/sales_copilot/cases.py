from __future__ import annotations

import json
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
    input_text: str
    expected_parse: ExpectedParse
    expected_workflow: ExpectedWorkflow


_TOP_LEVEL_FIELDS = ("case_id", "input_text", "expected_parse", "expected_workflow")
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


def load_golden_cases(path: str | Path) -> list[GoldenCase]:
    cases: list[GoldenCase] = []
    file_path = Path(path)

    with file_path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue

            record = json.loads(line)
            top_level = _ensure_object(record, f"line {line_number}")
            _validate_fields(top_level, _TOP_LEVEL_FIELDS, f"line {line_number}", "required_top_level_fields")

            expected_parse = _ensure_object(top_level["expected_parse"], f"line {line_number} expected_parse")
            _validate_fields(
                expected_parse,
                _EXPECTED_PARSE_FIELDS,
                f"line {line_number} expected_parse",
                "required_parse_fields",
            )

            expected_workflow = _ensure_object(
                top_level["expected_workflow"],
                f"line {line_number} expected_workflow",
            )
            _validate_fields(
                expected_workflow,
                _EXPECTED_WORKFLOW_FIELDS,
                f"line {line_number} expected_workflow",
                "required_workflow_fields",
            )

            cases.append(
                cast(
                    GoldenCase,
                    {
                        "case_id": top_level["case_id"],
                        "input_text": top_level["input_text"],
                        "expected_parse": cast(ExpectedParse, expected_parse),
                        "expected_workflow": cast(ExpectedWorkflow, expected_workflow),
                    },
                )
            )

    return cases
