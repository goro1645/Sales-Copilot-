from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evals.sales_copilot.metrics import _set_precision_recall_f1


TARGET_FIELDS = (
    "confirmed_needs",
    "budget_signals",
    "timeline_signals",
    "next_steps",
)

AI_REVIEW_TOOL_NAME = "submit_ai_calibrated_parse"

TARGET_BUCKETS = {
    "ordinary_stable": 25,
    "timeline_boundary": 20,
    "budget_boundary": 20,
    "field_overlap_high_risk": 20,
    "model_rule_conflict": 15,
}

_TIME_MARKERS = (
    "今天",
    "明天",
    "之后",
    "完成后",
    "订单完成后",
    "工作日内",
    "尽快",
    "稍后",
    "回电",
    "回复",
    "发货",
    "送达",
    "到账",
    "tomorrow",
    "today",
    "after",
    "within",
    "business day",
    "reply",
    "contact",
)

_BUDGET_MARKERS = (
    "退款",
    "补偿",
    "优惠券",
    "优惠",
    "差价",
    "返还",
    "价格",
    "费用",
    "价保",
    "发票",
    "tax",
    "coupon",
    "refund",
    "price",
    "discount",
    "compensation",
)

_FALLBACK_ORDER = {
    "budget_boundary": ("field_overlap_high_risk",),
    "timeline_boundary": ("field_overlap_high_risk",),
    "model_rule_conflict": ("field_overlap_high_risk",),
    "ordinary_stable": ("ordinary_stable",),
}


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            result.append(item.strip())
    return result


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _stringify_string_list(values: list[str]) -> str:
    return " | ".join(values) if values else "(empty)"


def _contains_any_marker(text: str, markers: tuple[str, ...]) -> bool:
    lowered = _normalize_text(text)
    return any(marker.lower() in lowered for marker in markers)


def _case_context_text(case: dict[str, object]) -> str:
    raw_row = case.get("_raw_row", {})
    parts = [str(case.get("meeting_note_text", ""))]
    if isinstance(raw_row, dict):
        for key in ("UserSumm", "AgentSumm", "FinalSumm"):
            parts.extend(_normalize_string_list(raw_row.get(key, [])))
    return "\n".join(part for part in parts if part).strip()


def _field_overlap_high_risk(case: dict[str, object]) -> bool:
    expected_parse = case.get("expected_parse", {})
    if not isinstance(expected_parse, dict):
        return False
    budget = set(_normalize_string_list(expected_parse.get("budget_signals", [])))
    timeline = set(_normalize_string_list(expected_parse.get("timeline_signals", [])))
    next_steps = set(_normalize_string_list(expected_parse.get("next_steps", [])))
    return bool((budget & next_steps) or (timeline & next_steps))


def _is_timeline_boundary(case: dict[str, object]) -> bool:
    return _contains_any_marker(_case_context_text(case), _TIME_MARKERS)


def _is_budget_boundary(case: dict[str, object]) -> bool:
    return _contains_any_marker(_case_context_text(case), _BUDGET_MARKERS)


def _target_field_conflict(case: dict[str, object], baseline_case_results: dict[str, dict[str, Any]]) -> bool:
    case_id = str(case.get("case_id", ""))
    baseline_result = baseline_case_results.get(case_id, {})
    if not isinstance(baseline_result, dict):
        return False
    parse_result = baseline_result.get("parse_result", {})
    expected_parse = case.get("expected_parse", {})
    if not isinstance(parse_result, dict) or not isinstance(expected_parse, dict):
        return False

    conflicting_fields = 0
    for field in TARGET_FIELDS:
        expected_values = _normalize_string_list(expected_parse.get(field, []))
        actual_values = _normalize_string_list(parse_result.get(field, []))
        if not expected_values and not actual_values:
            continue
        precision, recall, f1 = _set_precision_recall_f1(expected_values, actual_values)
        if f1 < 0.5:
            conflicting_fields += 1
    return conflicting_fields > 0


def _is_ordinary_stable(case: dict[str, object], baseline_case_results: dict[str, dict[str, Any]]) -> bool:
    return (
        not _field_overlap_high_risk(case)
        and not _is_timeline_boundary(case)
        and not _is_budget_boundary(case)
        and not _target_field_conflict(case, baseline_case_results)
    )


def _case_sort_key(case: dict[str, object]) -> tuple[str, str]:
    return (str(case.get("case_id", "")), str(case.get("source_uid", "")))


def load_case_results_by_id(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            if isinstance(payload, dict) and isinstance(payload.get("case_id"), str):
                rows[payload["case_id"]] = payload
    return rows


def _eligible_cases_for_bucket(
    bucket: str,
    cases: list[dict[str, object]],
    baseline_case_results: dict[str, dict[str, Any]],
) -> list[dict[str, object]]:
    if bucket == "ordinary_stable":
        predicate = lambda case: _is_ordinary_stable(case, baseline_case_results)
    elif bucket == "timeline_boundary":
        predicate = _is_timeline_boundary
    elif bucket == "budget_boundary":
        predicate = _is_budget_boundary
    elif bucket == "field_overlap_high_risk":
        predicate = _field_overlap_high_risk
    elif bucket == "model_rule_conflict":
        predicate = lambda case: _target_field_conflict(case, baseline_case_results)
    else:
        predicate = lambda case: False
    return [case for case in sorted(cases, key=_case_sort_key) if predicate(case)]


def build_calibrated_sample(
    cases: list[dict[str, object]],
    *,
    baseline_case_results: dict[str, dict[str, Any]],
    target_counts: dict[str, int] | None = None,
) -> list[dict[str, object]]:
    targets = dict(target_counts or TARGET_BUCKETS)
    selected_case_ids: set[str] = set()
    selected_rows: list[dict[str, object]] = []

    for bucket, target_count in targets.items():
        bucket_rows: list[dict[str, object]] = []
        primary_candidates = _eligible_cases_for_bucket(bucket, cases, baseline_case_results)
        for candidate in primary_candidates:
            case_id = str(candidate.get("case_id", ""))
            if case_id in selected_case_ids:
                continue
            row = dict(candidate)
            row["sampling_bucket"] = bucket
            bucket_rows.append(row)
            selected_case_ids.add(case_id)
            if len(bucket_rows) >= target_count:
                break

        if len(bucket_rows) < target_count:
            for fallback_bucket in _FALLBACK_ORDER.get(bucket, ()):
                fallback_candidates = _eligible_cases_for_bucket(fallback_bucket, cases, baseline_case_results)
                for candidate in fallback_candidates:
                    case_id = str(candidate.get("case_id", ""))
                    if case_id in selected_case_ids:
                        continue
                    row = dict(candidate)
                    row["sampling_bucket"] = bucket
                    bucket_rows.append(row)
                    selected_case_ids.add(case_id)
                    if len(bucket_rows) >= target_count:
                        break
                if len(bucket_rows) >= target_count:
                    break

        if len(bucket_rows) < target_count:
            remaining = [case for case in sorted(cases, key=_case_sort_key) if str(case.get("case_id", "")) not in selected_case_ids]
            for candidate in remaining:
                case_id = str(candidate.get("case_id", ""))
                row = dict(candidate)
                row["sampling_bucket"] = bucket
                bucket_rows.append(row)
                selected_case_ids.add(case_id)
                if len(bucket_rows) >= target_count:
                    break

        selected_rows.extend(bucket_rows)

    return selected_rows


def _build_review_correction(
    expected_values: list[str],
    baseline_values: list[str],
) -> tuple[str, list[str]]:
    if not expected_values and not baseline_values:
        return "keep", []

    precision, recall, f1 = _set_precision_recall_f1(expected_values, baseline_values)
    if f1 >= 0.95:
        return "keep", list(expected_values)
    if baseline_values:
        return "edit", list(baseline_values)
    if expected_values:
        return "keep", list(expected_values)
    return "drop", []


def _build_pre_annotation(
    case: dict[str, object],
    baseline_parse_result: dict[str, Any],
    *,
    sampling_bucket: str,
) -> dict[str, Any]:
    expected_parse = case.get("expected_parse", {})
    if not isinstance(expected_parse, dict):
        expected_parse = {}

    corrected_expected_parse: dict[str, list[str]] = {}
    decisions: dict[str, str] = {}

    for field in TARGET_FIELDS:
        decision, corrected_values = _build_review_correction(
            _normalize_string_list(expected_parse.get(field, [])),
            _normalize_string_list(baseline_parse_result.get(field, [])),
        )
        decisions[f"{field}_decision"] = decision
        corrected_expected_parse[field] = corrected_values

    edit_fields = [field for field in TARGET_FIELDS if decisions[f"{field}_decision"] != "keep"]
    if sampling_bucket == "ordinary_stable" and not edit_fields:
        confidence = "high"
    elif sampling_bucket in {"field_overlap_high_risk", "model_rule_conflict"} or len(edit_fields) >= 2:
        confidence = "low"
    else:
        confidence = "medium"

    review_reason = "auto_gold_vs_baseline_alignment"
    if sampling_bucket == "field_overlap_high_risk":
        review_reason = "field_overlap_high_risk"
    elif sampling_bucket == "model_rule_conflict":
        review_reason = "baseline_conflicts_with_auto_gold"
    elif sampling_bucket == "budget_boundary":
        review_reason = "budget_boundary_case"
    elif sampling_bucket == "timeline_boundary":
        review_reason = "timeline_boundary_case"

    return {
        **decisions,
        "corrected_expected_parse": corrected_expected_parse,
        "confidence": confidence,
        "needs_human_review": bool(edit_fields or sampling_bucket != "ordinary_stable"),
        "review_reason": review_reason,
        "review_note": "",
    }


def build_calibrated_working_rows(
    cases: list[dict[str, object]],
    *,
    baseline_case_results: dict[str, dict[str, Any]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for case in cases:
        case_id = str(case.get("case_id", ""))
        baseline_case = baseline_case_results.get(case_id, {})
        baseline_parse_result = baseline_case.get("parse_result", {})
        if not isinstance(baseline_parse_result, dict):
            baseline_parse_result = {}

        raw_row = case.get("_raw_row", {})
        if not isinstance(raw_row, dict):
            raw_row = {}

        sampling_bucket = str(case.get("sampling_bucket", "ordinary_stable"))
        rows.append(
            {
                "case_id": case.get("case_id", ""),
                "source_uid": case.get("source_uid", ""),
                "source_split": case.get("source_split", ""),
                "source_note": case.get("source_note", ""),
                "sampling_bucket": sampling_bucket,
                "customer_profile_text": case.get("customer_profile_text", ""),
                "meeting_note_text": case.get("meeting_note_text", ""),
                "user_summ": _normalize_string_list(raw_row.get("UserSumm", [])),
                "agent_summ": _normalize_string_list(raw_row.get("AgentSumm", [])),
                "final_summ": _normalize_string_list(raw_row.get("FinalSumm", [])),
                "auto_expected_parse": case.get("expected_parse", {}),
                "baseline_parse_result": baseline_parse_result,
                "pre_annotation": _build_pre_annotation(
                    case,
                    baseline_parse_result,
                    sampling_bucket=sampling_bucket,
                ),
                "human_review": {},
            }
        )
    return rows


def export_final_calibrated_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    final_rows: list[dict[str, Any]] = []
    for row in rows:
        auto_expected_parse = row.get("auto_expected_parse", row.get("expected_parse", {}))
        if not isinstance(auto_expected_parse, dict):
            auto_expected_parse = {}

        pre_annotation = row.get("pre_annotation", {})
        if not isinstance(pre_annotation, dict):
            pre_annotation = {}
        corrected_expected = pre_annotation.get("corrected_expected_parse", {})
        if not isinstance(corrected_expected, dict):
            corrected_expected = {}

        human_review = row.get("human_review", {})
        if not isinstance(human_review, dict):
            human_review = {}
        human_expected = human_review.get("final_expected_parse", {})
        if not isinstance(human_expected, dict):
            human_expected = {}

        expected_parse = dict(auto_expected_parse)
        for field in TARGET_FIELDS:
            if field in human_expected:
                expected_parse[field] = _normalize_string_list(human_expected.get(field, []))
            elif field in corrected_expected:
                expected_parse[field] = _normalize_string_list(corrected_expected.get(field, []))

        final_rows.append(
            {
                "case_id": row.get("case_id", ""),
                "source_uid": row.get("source_uid", ""),
                "source_split": row.get("source_split", ""),
                "meeting_note_text": row.get("meeting_note_text", ""),
                "customer_profile_text": row.get("customer_profile_text", ""),
                "expected_parse": expected_parse,
            }
        )
    return final_rows


def build_ai_calibration_tools() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": AI_REVIEW_TOOL_NAME,
                "description": "Return the final AI-calibrated expected_parse for the target Sales Copilot fields.",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "corrected_expected_parse": {
                            "type": "object",
                            "properties": {
                                field: {
                                    "type": "array",
                                    "items": {"type": "string"},
                                }
                                for field in TARGET_FIELDS
                            },
                            "required": list(TARGET_FIELDS),
                            "additionalProperties": False,
                        }
                    },
                    "required": ["corrected_expected_parse"],
                    "additionalProperties": False,
                },
            },
        }
    ]


def build_ai_calibration_messages(row: dict[str, Any]) -> list[dict[str, str]]:
    auto_expected_parse = row.get("auto_expected_parse", {})
    if not isinstance(auto_expected_parse, dict):
        auto_expected_parse = {}

    baseline_parse_result = row.get("baseline_parse_result", {})
    if not isinstance(baseline_parse_result, dict):
        baseline_parse_result = {}

    pre_annotation = row.get("pre_annotation", {})
    if not isinstance(pre_annotation, dict):
        pre_annotation = {}
    corrected_expected = pre_annotation.get("corrected_expected_parse", {})
    if not isinstance(corrected_expected, dict):
        corrected_expected = {}

    lines = [
        f"case_id: {row.get('case_id', '')}",
        f"sampling_bucket: {row.get('sampling_bucket', '')}",
        "",
        "meeting_note_text:",
        str(row.get("meeting_note_text", "")),
        "",
        "user_summ:",
        _stringify_string_list(_normalize_string_list(row.get("user_summ", []))),
        "",
        "agent_summ:",
        _stringify_string_list(_normalize_string_list(row.get("agent_summ", []))),
        "",
        "final_summ:",
        _stringify_string_list(_normalize_string_list(row.get("final_summ", []))),
        "",
        "auto_expected_parse:",
    ]
    for field in TARGET_FIELDS:
        lines.append(f"- {field}: {_stringify_string_list(_normalize_string_list(auto_expected_parse.get(field, [])))}")
    lines.append("")
    lines.append("baseline_parse_result:")
    for field in TARGET_FIELDS:
        lines.append(f"- {field}: {_stringify_string_list(_normalize_string_list(baseline_parse_result.get(field, [])))}")
    lines.append("")
    lines.append("pre_annotation.corrected_expected_parse:")
    for field in TARGET_FIELDS:
        lines.append(f"- {field}: {_stringify_string_list(_normalize_string_list(corrected_expected.get(field, [])))}")
    lines.append("")
    lines.append("Return the most semantically faithful final field values for the four target fields only.")
    lines.append("Use concise field-appropriate phrases. Prefer clean field assignment over copying weak-gold overlaps.")
    lines.append("Do not change account_name, customer_roles, or competitors here.")

    return [
        {
            "role": "system",
            "content": (
                "You are calibrating a Sales Copilot benchmark draft. "
                "Review the raw conversation summary plus weak auto-gold, baseline parse, "
                "and pre-annotation. Then call the tool with the final corrected_expected_parse. "
                "Each field must be a list of concise strings. "
                "budget_signals only contains price/refund/coupon/compensation signals. "
                "timeline_signals only contains time/order/duration constraints. "
                "next_steps only contains follow-up actions or promises."
            ),
        },
        {"role": "user", "content": "\n".join(lines)},
    ]


def _normalize_ai_corrected_expected_parse(
    corrected_expected_parse: dict[str, Any],
    row: dict[str, Any],
) -> dict[str, list[str]]:
    if not isinstance(corrected_expected_parse, dict):
        raise ValueError("AI corrected_expected_parse must be a dict")

    pre_annotation = row.get("pre_annotation", {})
    if not isinstance(pre_annotation, dict):
        pre_annotation = {}
    pre_corrected = pre_annotation.get("corrected_expected_parse", {})
    if not isinstance(pre_corrected, dict):
        pre_corrected = {}

    normalized: dict[str, list[str]] = {}
    for field in TARGET_FIELDS:
        value = corrected_expected_parse.get(field)
        if value is None:
            value = pre_corrected.get(field, [])
        normalized[field] = _normalize_string_list(value)
    return normalized


def fill_ai_review_for_row(
    row: dict[str, Any],
    *,
    llm_client: Any,
) -> dict[str, Any]:
    tool_result = llm_client.complete_with_tool(
        build_ai_calibration_messages(row),
        tools=build_ai_calibration_tools(),
        tool_choice={"type": "function", "function": {"name": AI_REVIEW_TOOL_NAME}},
    )

    tool_name = tool_result.get("tool_name")
    if tool_name != AI_REVIEW_TOOL_NAME:
        raise ValueError(f"Unexpected AI calibration tool call: {tool_name}")

    arguments = tool_result.get("arguments", {})
    if not isinstance(arguments, dict):
        raise ValueError("AI calibration arguments must be a dict")

    corrected = _normalize_ai_corrected_expected_parse(arguments.get("corrected_expected_parse", {}), row)

    updated = dict(row)
    updated["human_review"] = {
        "final_expected_parse": corrected,
        "reviewed_by": "ai",
        "review_status": "completed",
        "review_note": "AI-calibrated draft produced with DeepSeek tool-call review.",
    }
    return updated


def fill_ai_review_rows(
    rows: list[dict[str, Any]],
    *,
    llm_client: Any,
) -> list[dict[str, Any]]:
    return [fill_ai_review_for_row(row, llm_client=llm_client) for row in rows]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
