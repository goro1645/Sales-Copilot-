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


def _is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


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


def _gold_list_field_applicability(expected_parse: dict[str, Any]) -> dict[str, bool]:
    return {field: bool(_normalize_list(expected_parse.get(field, []))) for field in LIST_FIELDS}


def _gold_risk_flag_applicability(case: dict[str, Any]) -> bool:
    return bool(_required_risk_flags(case))


def _invalid_parse_metrics(case: dict[str, Any]) -> dict[str, Any]:
    expected_parse = case.get("expected_parse", {})
    if not isinstance(expected_parse, dict):
        expected_parse = {}

    # 解析无效时，仍按 gold 是否要求该字段来计入平均，避免 0 分样本被分母漏掉。
    return {
        "json_valid": False,
        "field_exact_match": {field: 0.0 for field in SCALAR_FIELDS},
        "list_field_precision": {field: 0.0 for field in LIST_FIELDS},
        "list_field_recall": {field: 0.0 for field in LIST_FIELDS},
        "list_field_f1": {field: 0.0 for field in LIST_FIELDS},
        "list_field_applicable": _gold_list_field_applicability(expected_parse),
        "risk_flag_recall": 0.0,
        "risk_flag_applicable": _gold_risk_flag_applicability(case),
    }


def _is_valid_actual_parse(actual_parse: dict[str, Any]) -> bool:
    if not isinstance(actual_parse.get("account_name"), str):
        return False
    for field in LIST_FIELDS:
        if not _is_string_list(actual_parse.get(field)):
            return False
    if not _is_string_list(actual_parse.get("risk_flags", [])):
        return False
    return True


def evaluate_parse_case(case: dict[str, Any], actual_parse: Any) -> dict[str, Any]:
    expected_parse = case.get("expected_parse", {})
    if not isinstance(expected_parse, dict):
        expected_parse = {}

    if not isinstance(actual_parse, dict):
        return _invalid_parse_metrics(case)

    if not _is_valid_actual_parse(actual_parse):
        return _invalid_parse_metrics(case)

    field_exact_match = {
        "account_name": expected_parse.get("account_name") == actual_parse.get("account_name")
    }

    list_field_precision: dict[str, float] = {}
    list_field_recall: dict[str, float] = {}
    list_field_f1: dict[str, float] = {}
    list_field_applicable: dict[str, bool] = {}
    for field in LIST_FIELDS:
        expected_values = _normalize_list(expected_parse.get(field, []))
        actual_values = _normalize_list(actual_parse.get(field, []))
        applicable = bool(expected_values or actual_values)
        if applicable:
            precision, recall, f1 = _set_precision_recall_f1(expected_values, actual_values)
        else:
            precision, recall, f1 = 0.0, 0.0, 0.0
        list_field_precision[field] = precision
        list_field_recall[field] = recall
        list_field_f1[field] = f1
        list_field_applicable[field] = applicable

    risk_flags = _normalize_list(actual_parse.get("risk_flags", []))
    required_risk_flags = _required_risk_flags(case)
    risk_flag_applicable = bool(required_risk_flags)
    if not risk_flag_applicable:
        risk_flag_recall = 0.0
    else:
        risk_flag_recall = len(set(required_risk_flags) & set(risk_flags)) / len(set(required_risk_flags))

    return {
        "json_valid": True,
        "field_exact_match": field_exact_match,
        "list_field_precision": list_field_precision,
        "list_field_recall": list_field_recall,
        "list_field_f1": list_field_f1,
        "list_field_applicable": list_field_applicable,
        "risk_flag_recall": risk_flag_recall,
        "risk_flag_applicable": risk_flag_applicable,
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
        list_field_applicable = row.get("list_field_applicable", {})
        if isinstance(list_field_f1, dict):
            list_field_f1_values.extend(
                float(list_field_f1.get(field, 0.0))
                for field in LIST_FIELDS
                if isinstance(list_field_applicable, dict) and list_field_applicable.get(field, False)
            )

    average_list_field_f1 = sum(list_field_f1_values) / len(list_field_f1_values) if list_field_f1_values else 0.0
    risk_flag_values = [
        float(row.get("risk_flag_recall", 0.0))
        for row in rows
        if row.get("risk_flag_applicable", False)
    ]
    risk_flag_recall = sum(risk_flag_values) / len(risk_flag_values) if risk_flag_values else 0.0

    return {
        "json_valid_rate": json_valid_rate,
        "field_exact_match_rate": field_exact_match_rate,
        "average_list_field_f1": average_list_field_f1,
        "risk_flag_recall": risk_flag_recall,
    }
