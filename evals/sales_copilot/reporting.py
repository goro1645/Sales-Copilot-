from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _format_percent(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.1%}"
    return "N/A"


def _build_report_markdown(bundle: dict[str, Any]) -> str:
    summary = bundle.get("summary", {})
    parse_summary = summary.get("parse_summary", {})
    workflow_summary = summary.get("workflow_summary", {})
    lines = [
        "# Sales Copilot Offline Eval Report",
        "",
        f"- Total cases: {summary.get('total_cases', 0)}",
        f"- Parse JSON valid rate: {_format_percent(parse_summary.get('json_valid_rate'))}",
        f"- Workflow success rate: {_format_percent(workflow_summary.get('workflow_success_rate'))}",
        "",
        "## Cases",
        "",
    ]
    for row in bundle.get("case_results", []):
        lines.extend(
            [
                f"### {row.get('case_id', 'unknown')}",
                f"- Segment: {row.get('segment', 'unknown')}",
                f"- Parse JSON valid: {row.get('parse_metrics', {}).get('json_valid', False)}",
                f"- Workflow success: {row.get('workflow_metrics', {}).get('workflow_success', False)}",
                "",
            ]
        )
    return "\n".join(lines)


def write_report_bundle(bundle, output_root) -> dict[str, str]:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)

    report_json = root / "report.json"
    report_md = root / "report.md"
    case_results_jsonl = root / "case_results.jsonl"

    # 这里同时落结构化和可读报告，方便脚本消费与人工快速浏览。
    report_json.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    report_md.write_text(_build_report_markdown(bundle), encoding="utf-8")
    with case_results_jsonl.open("w", encoding="utf-8") as handle:
        for row in bundle.get("case_results", []):
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    return {
        "report_json": str(report_json),
        "report_md": str(report_md),
        "case_results_jsonl": str(case_results_jsonl),
    }
