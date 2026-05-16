from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from evals.sales_copilot.csds_adapter import load_full_csds_cases


DEFAULT_BUCKET_TARGETS = {
    "ordinary": 15,
    "timeline_nonempty": 15,
    "budget_nonempty": 10,
    "field_overlap_high_risk": 10,
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
    "税号",
)


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            result.append(item.strip())
    return result


def _has_any_marker(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _load_raw_csds_split_rows(dataset_dir: Path, split: str) -> dict[str, dict[str, Any]]:
    split_path = Path(dataset_dir) / f"{split}.json"
    payload = json.loads(split_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"split file must contain a JSON list: {split_path}")
    rows: dict[str, dict[str, Any]] = {}
    for row in payload:
        if not isinstance(row, dict):
            continue
        dialogue_id = str(row.get("DialogueID", "")).strip()
        if dialogue_id:
            rows[dialogue_id] = row
    return rows


def assign_audit_bucket(case: dict[str, object]) -> str:
    expected_parse = case.get("expected_parse", {})
    if not isinstance(expected_parse, dict):
        expected_parse = {}

    budget = set(_normalize_string_list(expected_parse.get("budget_signals", [])))
    timeline = set(_normalize_string_list(expected_parse.get("timeline_signals", [])))
    next_steps = set(_normalize_string_list(expected_parse.get("next_steps", [])))

    if timeline & next_steps or budget & next_steps:
        return "field_overlap_high_risk"
    if timeline:
        return "timeline_nonempty"
    if budget:
        return "budget_nonempty"
    return "ordinary"


def build_audit_row(
    case: dict[str, object],
    *,
    raw_row: dict[str, Any] | None = None,
    audit_bucket: str | None = None,
) -> dict[str, object]:
    expected_parse = case.get("expected_parse", {})
    if not isinstance(expected_parse, dict):
        expected_parse = {}

    budget = _normalize_string_list(expected_parse.get("budget_signals", []))
    timeline = _normalize_string_list(expected_parse.get("timeline_signals", []))
    next_steps = _normalize_string_list(expected_parse.get("next_steps", []))

    timeline_set = set(timeline)
    budget_set = set(budget)
    next_steps_set = set(next_steps)

    raw_row = raw_row or {}
    user_summ = _normalize_string_list(raw_row.get("UserSumm", []))
    agent_summ = _normalize_string_list(raw_row.get("AgentSumm", []))
    final_summ = _normalize_string_list(raw_row.get("FinalSumm", []))

    heuristic_flags = {
        "timeline_next_overlap": bool(timeline_set & next_steps_set),
        "budget_next_overlap": bool(budget_set & next_steps_set),
        "timeline_contains_non_time_like_sentence": any(not _has_any_marker(text, _TIME_MARKERS) for text in timeline),
        "budget_contains_non_budget_like_sentence": any(not _has_any_marker(text, _BUDGET_MARKERS) for text in budget),
        "next_steps_contains_budget_sentence": any(_has_any_marker(text, _BUDGET_MARKERS) for text in next_steps),
    }

    return {
        "case_id": case.get("case_id", ""),
        "source_uid": case.get("source_uid", ""),
        "source_split": case.get("source_split", ""),
        "audit_bucket": audit_bucket or assign_audit_bucket(case),
        "meeting_note_text": case.get("meeting_note_text", ""),
        "user_summ": user_summ,
        "agent_summ": agent_summ,
        "final_summ": final_summ,
        "expected_parse": expected_parse,
        "heuristic_flags": heuristic_flags,
        "audit_label": "",
        "audit_note": "",
    }


def build_stratified_audit_sample(
    cases: list[dict[str, object]],
    *,
    bucket_targets: dict[str, int] | None = None,
    raw_rows_by_uid: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, object]]:
    targets = bucket_targets or DEFAULT_BUCKET_TARGETS
    grouped: dict[str, list[dict[str, object]]] = {bucket: [] for bucket in targets}
    for case in sorted(cases, key=lambda row: str(row.get("case_id", ""))):
        bucket = assign_audit_bucket(case)
        if bucket in grouped:
            grouped[bucket].append(case)

    rows: list[dict[str, object]] = []
    for bucket, target_count in targets.items():
        for case in grouped.get(bucket, [])[:target_count]:
            source_uid = str(case.get("source_uid", ""))
            raw_row = (raw_rows_by_uid or {}).get(source_uid)
            rows.append(build_audit_row(case, raw_row=raw_row, audit_bucket=bucket))
    return rows


def summarize_gold_audit_rows(rows: list[dict[str, object]]) -> dict[str, object]:
    bucket_counts = Counter(str(row.get("audit_bucket", "unknown")) for row in rows)
    flag_counts: Counter[str] = Counter()
    for row in rows:
        flags = row.get("heuristic_flags", {})
        if not isinstance(flags, dict):
            continue
        for key, value in flags.items():
            if value:
                flag_counts[str(key)] += 1

    return {
        "total_rows": len(rows),
        "bucket_counts": dict(bucket_counts),
        "heuristic_flag_counts": dict(flag_counts),
    }


def generate_full_csds_gold_audit(
    dataset_dir: Path,
    *,
    split: str = "test",
    bucket_targets: dict[str, int] | None = None,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    dataset_root = Path(dataset_dir)
    cases = load_full_csds_cases(dataset_root, splits=[split])
    raw_rows_by_uid = _load_raw_csds_split_rows(dataset_root, split)
    rows = build_stratified_audit_sample(cases, bucket_targets=bucket_targets, raw_rows_by_uid=raw_rows_by_uid)
    summary = summarize_gold_audit_rows(rows)
    return rows, summary
