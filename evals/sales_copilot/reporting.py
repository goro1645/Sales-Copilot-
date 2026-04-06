from __future__ import annotations

import datetime as dt
import json
from collections import Counter
from pathlib import Path
from typing import Any


def _collect_failing_cases(case_results: list[dict[str, Any]]) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    for row in case_results:
        reasons: list[str] = []
        parse_metrics = row.get("parse_metrics", {})
        workflow_metrics = row.get("workflow_metrics", {})
        if not parse_metrics.get("json_valid", False):
            reasons.append("parse json invalid")
        if workflow_metrics.get("route_correct") is False:
            reasons.append("route mismatch")
        if workflow_metrics.get("score_in_range") is False:
            reasons.append("lead score out of range")
        if workflow_metrics.get("required_task_hit_rate", 1.0) not in (1, 1.0):
            reasons.append("required tasks missing")
        if reasons:
            failures.append(
                {
                    "case_id": str(row.get("case_id", "unknown")),
                    "reason": "; ".join(reasons),
                }
            )
    return failures


def _build_report_markdown(bundle: dict[str, Any]) -> str:
    summary = bundle.get("summary", {})
    parse_summary = summary.get("parse", {})
    workflow_summary = summary.get("workflow", {})
    case_results = bundle.get("case_results", [])
    segment_distribution = Counter(str(row.get("segment", "unknown")) for row in case_results)
    lines = [
        "# Sales Copilot Offline Eval Report",
        "",
        "## Overview",
        "",
        f"- Dataset size: {summary.get('total_cases', 0)}",
        f"- Cases file: {bundle.get('cases_path', 'N/A')}",
        "",
        "## Segment Distribution",
        "",
        "| segment | count |",
        "| --- | --- |",
    ]
    for segment, count in sorted(segment_distribution.items()):
        lines.append(f"| {segment} | {count} |")

    lines.extend(
        [
            "",
            "## Parse Metrics",
            "",
            "| metric | value |",
            "| --- | --- |",
        ]
    )
    for key in ("json_valid_rate", "average_list_field_f1", "risk_flag_recall"):
        lines.append(f"| {key} | {parse_summary.get(key, 'N/A')} |")
    field_exact_match_rate = parse_summary.get("field_exact_match_rate", {})
    if isinstance(field_exact_match_rate, dict):
        for key, value in field_exact_match_rate.items():
            lines.append(f"| field_exact_match_rate.{key} | {value} |")

    lines.extend(
        [
            "",
            "## Workflow Metrics",
            "",
            "| metric | value |",
            "| --- | --- |",
        ]
    )
    for key in (
        "workflow_success_rate",
        "route_accuracy",
        "priority_accuracy",
        "stage_accuracy",
        "score_range_accuracy",
        "crm_writeback_accuracy",
        "task_generation_hit_rate",
        "required_task_hit_rate",
    ):
        lines.append(f"| {key} | {workflow_summary.get(key, 'N/A')} |")

    lines.extend(
        [
            "",
            "## Top Failing Cases",
            "",
        ]
    )
    failing_cases = _collect_failing_cases(case_results)
    if not failing_cases:
        lines.append("- None")
    else:
        for item in failing_cases[:5]:
            lines.append(f"- {item['case_id']}: {item['reason']}")
    return "\n".join(lines)


def write_report_bundle(bundle, output_root) -> str:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    report_dir = root / dt.datetime.now().strftime("%Y%m%d%H%M%S")
    report_dir.mkdir(parents=True, exist_ok=False)

    report_json = report_dir / "report.json"
    report_md = report_dir / "report.md"
    case_results_jsonl = report_dir / "case_results.jsonl"

    # 这里把每次评测落到独立时间戳目录，便于保留完整 bundle 和逐条明细。
    report_json.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    report_md.write_text(_build_report_markdown(bundle), encoding="utf-8")
    with case_results_jsonl.open("w", encoding="utf-8") as handle:
        for row in bundle.get("case_results", []):
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return str(report_dir)
