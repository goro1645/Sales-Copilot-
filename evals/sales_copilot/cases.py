from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict


class ExpectedParse(TypedDict):
    intent: str
    confidence: float


class ExpectedWorkflow(TypedDict):
    route: str
    required_workflow_fields: list[str]


class GoldenCase(TypedDict):
    case_id: str
    input_text: str
    expected_parse: ExpectedParse
    expected_workflow: ExpectedWorkflow


_TOP_LEVEL_FIELDS = ("case_id", "input_text", "expected_parse", "expected_workflow")
_EXPECTED_PARSE_FIELDS = ("intent", "confidence")
_EXPECTED_WORKFLOW_FIELDS = ("route", "required_workflow_fields")


def _missing_fields(data: dict[str, object], required_fields: tuple[str, ...]) -> list[str]:
    return [field for field in required_fields if field not in data]


def _ensure_object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _validate_fields(data: dict[str, object], required_fields: tuple[str, ...], label: str) -> None:
    missing_fields = _missing_fields(data, required_fields)
    if missing_fields:
        raise ValueError(f"{label} missing required fields: {', '.join(missing_fields)}")


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
            _validate_fields(top_level, _TOP_LEVEL_FIELDS, f"line {line_number}")

            expected_parse = _ensure_object(top_level["expected_parse"], f"line {line_number} expected_parse")
            _validate_fields(expected_parse, _EXPECTED_PARSE_FIELDS, f"line {line_number} expected_parse")

            expected_workflow = _ensure_object(
                top_level["expected_workflow"],
                f"line {line_number} expected_workflow",
            )
            _validate_fields(
                expected_workflow,
                _EXPECTED_WORKFLOW_FIELDS,
                f"line {line_number} expected_workflow",
            )

            # 这里把字典原样返回，方便评测代码直接按键读取。
            cases.append(top_level)  # type: ignore[arg-type]

    return cases
