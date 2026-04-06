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
WORKFLOW_ROUTES = (
    "need_more_info",
    "low_priority_nurture",
    "standard_follow_up",
    "high_priority_follow_up",
)


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


def _get_value(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _normalize_route(value: Any) -> str:
    text = _normalize_text(value).replace("-", "_").replace(" ", "_")
    if not text:
        return ""
    if text in WORKFLOW_ROUTES:
        return text
    if "need_more_info" in text or "needmoreinfo" in text:
        return "need_more_info"
    if "low_priority_nurture" in text or "lowprioritynurture" in text:
        return "low_priority_nurture"
    if "standard_follow_up" in text or "standardfollowup" in text:
        return "standard_follow_up"
    if "high_priority_follow_up" in text or "highpriorityfollowup" in text:
        return "high_priority_follow_up"
    return ""


def _extract_workflow_route(workflow_log: Any) -> str:
    if isinstance(workflow_log, dict):
        candidates = [workflow_log]
    elif isinstance(workflow_log, list):
        candidates = workflow_log
    else:
        candidates = [workflow_log]

    for entry in candidates:
        route = _normalize_route(_get_value(entry, "route", ""))
        if route:
            return route
        route = _normalize_route(_get_value(entry, "expected_route", ""))
        if route:
            return route
        route = _normalize_route(_get_value(entry, "decision_route", ""))
        if route:
            return route
        route = _normalize_route(_get_value(entry, "next_route", ""))
        if route:
            return route
        route = _normalize_route(entry)
        if route:
            return route
    return ""


def _extract_task_titles(task_payload: Any) -> list[str]:
    if not isinstance(task_payload, list):
        return []

    titles: list[str] = []
    seen: set[str] = set()
    for item in task_payload:
        title = _normalize_text(_get_value(item, "title", _get_value(item, "task_title", item)))
        if not title or title in seen:
            continue
        seen.add(title)
        titles.append(title)
    return titles


def _task_title_matches(required_title: str, actual_title: str) -> bool:
    required = _normalize_text(required_title)
    actual = _normalize_text(actual_title)
    if not required or not actual:
        return False
    return required in actual or actual in required


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


def evaluate_workflow_case(case: dict[str, Any], actual_result: Any) -> dict[str, Any]:
    expected_workflow = case.get("expected_workflow", {})
    if not isinstance(expected_workflow, dict):
        expected_workflow = {}

    if not isinstance(actual_result, dict):
        actual_result = {}

    expected_route = _normalize_route(expected_workflow.get("expected_route"))
    actual_route = _extract_workflow_route(actual_result.get("workflow_log", actual_result.get("workflow_logs")))
    if not actual_route:
        actual_route = _normalize_route(actual_result.get("route"))

    score_range = expected_workflow.get("lead_score_range", [])
    if isinstance(score_range, list) and len(score_range) == 2:
        score_min, score_max = score_range
    else:
        score_min, score_max = 0, 0

    score_value = actual_result.get("lead_score", actual_result.get("score"))
    score_in_range = isinstance(score_value, (int, float)) and not isinstance(score_value, bool) and score_min <= score_value <= score_max

    priority_value = actual_result.get("lead_priority", actual_result.get("priority"))
    stage_value = actual_result.get("opportunity_stage", actual_result.get("stage"))
    priority_correct = _normalize_text(priority_value) == _normalize_text(expected_workflow.get("lead_priority"))
    stage_correct = _normalize_text(stage_value) == _normalize_text(expected_workflow.get("opportunity_stage"))

    crm_update_ids = actual_result.get("crm_update_ids")
    if crm_update_ids is None:
        crm_update_ids = actual_result.get("crm_writeback")
    crm_writeback_actual = bool(crm_update_ids)
    crm_writeback_correct = crm_writeback_actual == bool(expected_workflow.get("should_write_crm"))

    task_payload = actual_result.get("task_payload", [])
    actual_task_titles = _extract_task_titles(task_payload)
    task_generation_correct = bool(actual_task_titles) == bool(expected_workflow.get("should_generate_tasks"))

    required_task_titles = _normalize_list(expected_workflow.get("required_task_titles", []))
    required_task_applicable = bool(required_task_titles)
    if required_task_applicable:
        matched_count = sum(
            1 for required_title in required_task_titles if any(_task_title_matches(required_title, actual_title) for actual_title in actual_task_titles)
        )
        required_task_hit_rate = matched_count / len(required_task_titles)
    else:
        required_task_hit_rate = 0.0

    route_correct = actual_route == expected_route if expected_route else False
    workflow_success = bool(actual_result) and (
        bool(actual_route)
        or score_value is not None
        or priority_value is not None
        or stage_value is not None
        or crm_update_ids is not None
        or bool(task_payload)
    )

    return {
        "workflow_success": workflow_success,
        "route_correct": route_correct,
        "priority_correct": priority_correct,
        "stage_correct": stage_correct,
        "score_in_range": score_in_range,
        "crm_writeback_correct": crm_writeback_correct,
        "task_generation_correct": task_generation_correct,
        "required_task_hit_rate": required_task_hit_rate,
        "required_task_applicable": required_task_applicable,
    }


def summarize_workflow_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    if total == 0:
        return {
            "workflow_success_rate": 0.0,
            "route_accuracy": 0.0,
            "priority_accuracy": 0.0,
            "stage_accuracy": 0.0,
            "score_range_accuracy": 0.0,
            "crm_writeback_accuracy": 0.0,
            "task_generation_hit_rate": 0.0,
            "required_task_hit_rate": 0.0,
        }

    def _rate(field: str) -> float:
        return sum(1.0 for row in rows if row.get(field)) / total

    required_task_values = [
        float(row.get("required_task_hit_rate", 0.0))
        for row in rows
        if row.get("required_task_applicable", False)
    ]

    return {
        "workflow_success_rate": _rate("workflow_success"),
        "route_accuracy": _rate("route_correct"),
        "priority_accuracy": _rate("priority_correct"),
        "stage_accuracy": _rate("stage_correct"),
        "score_range_accuracy": _rate("score_in_range"),
        "crm_writeback_accuracy": _rate("crm_writeback_correct"),
        "task_generation_hit_rate": _rate("task_generation_correct"),
        "required_task_hit_rate": sum(required_task_values) / len(required_task_values) if required_task_values else 0.0,
    }
