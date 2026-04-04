from __future__ import annotations

from collections.abc import Iterable
from typing import Any


LIST_FIELDS = (
    "customer_roles",
    "confirmed_needs",
    "budget_signals",
    "timeline_signals",
    "next_steps",
    "competitors",
)
SCALAR_FIELDS = ("account_name",)


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _normalize_list(value: Any) -> list[str]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes, dict)):
        return []

    items: list[str] = []
    seen: set[str] = set()
    for item in value:
        normalized = _normalize_text(item)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        items.append(normalized)
    return items


def _set_precision_recall_f1(expected: list[str], actual: list[str]) -> tuple[float, float, float]:
    expected_set = set(expected)
    actual_set = set(actual)

    if not expected_set and not actual_set:
        return 1.0, 1.0, 1.0
    if not expected_set or not actual_set:
        return 0.0, 0.0, 0.0

    true_positive = len(expected_set & actual_set)
    precision = true_positive / len(actual_set)
    recall = true_positive / len(expected_set)
    if precision + recall == 0:
        return precision, recall, 0.0
    f1 = 2 * precision * recall / (precision + recall)
    return precision, recall, f1


def _required_risk_flags(case: dict[str, Any]) -> list[str]:
    expected_workflow = case.get("expected_workflow", {})
    if not isinstance(expected_workflow, dict):
        return []
    return _normalize_list(expected_workflow.get("required_risk_flags", []))


def evaluate_parse_case(case: dict[str, Any], actual_parse: Any) -> dict[str, Any]:
    expected_parse = case.get("expected_parse", {})
    if not isinstance(expected_parse, dict):
        expected_parse = {}

    if not isinstance(actual_parse, dict):
        return {
            "json_valid": False,
            "field_exact_match": {field: 0.0 for field in SCALAR_FIELDS},
            "list_field_precision": {field: 0.0 for field in LIST_FIELDS},
            "list_field_recall": {field: 0.0 for field in LIST_FIELDS},
            "list_field_f1": {field: 0.0 for field in LIST_FIELDS},
            "risk_flag_recall": 0.0,
        }

    field_exact_match = {
        "account_name": _normalize_text(expected_parse.get("account_name"))
        == _normalize_text(actual_parse.get("account_name"))
    }

    list_field_precision: dict[str, float] = {}
    list_field_recall: dict[str, float] = {}
    list_field_f1: dict[str, float] = {}
    for field in LIST_FIELDS:
        precision, recall, f1 = _set_precision_recall_f1(
            _normalize_list(expected_parse.get(field, [])),
            _normalize_list(actual_parse.get(field, [])),
        )
        list_field_precision[field] = precision
        list_field_recall[field] = recall
        list_field_f1[field] = f1

    risk_flags = _normalize_list(actual_parse.get("risk_flags", []))
    required_risk_flags = _required_risk_flags(case)
    if not required_risk_flags:
        risk_flag_recall = 1.0
    else:
        risk_flag_recall = len(set(required_risk_flags) & set(risk_flags)) / len(set(required_risk_flags))

    return {
        "json_valid": True,
        "field_exact_match": field_exact_match,
        "list_field_precision": list_field_precision,
        "list_field_recall": list_field_recall,
        "list_field_f1": list_field_f1,
        "risk_flag_recall": risk_flag_recall,
    }


def summarize_parse_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    if total == 0:
        return {
            "json_valid_rate": 0.0,
            "field_exact_match_rate": {field: 0.0 for field in SCALAR_FIELDS},
            "average_list_field_f1": 0.0,
            "risk_flag_recall": 0.0,
        }

    json_valid_rate = sum(1.0 for row in rows if row.get("json_valid")) / total

    field_exact_match_rate: dict[str, float] = {}
    for field in SCALAR_FIELDS:
        field_exact_match_rate[field] = sum(
            1.0 if row.get("field_exact_match", {}).get(field, False) else 0.0 for row in rows
        ) / total

    list_field_f1_values: list[float] = []
    for row in rows:
        list_field_f1 = row.get("list_field_f1", {})
        if isinstance(list_field_f1, dict):
            list_field_f1_values.extend(float(list_field_f1.get(field, 0.0)) for field in LIST_FIELDS)

    average_list_field_f1 = sum(list_field_f1_values) / len(list_field_f1_values) if list_field_f1_values else 0.0
    risk_flag_recall = sum(float(row.get("risk_flag_recall", 0.0)) for row in rows) / total

    return {
        "json_valid_rate": json_valid_rate,
        "field_exact_match_rate": field_exact_match_rate,
        "average_list_field_f1": average_list_field_f1,
        "risk_flag_recall": risk_flag_recall,
    }
