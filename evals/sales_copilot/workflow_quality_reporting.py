"""Workflow-quality report aggregation for LLM-judge outputs.

This file is where judge scores become the headline rates we talk about later:
- `overall_acceptable_rate`
- `crm_acceptable_rate`
- `task_acceptable_rate`
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any


def summarize_workflow_quality_results(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    # 这些 acceptable rate 不是模型直接输出的，而是从 judge 的 1-5 分数阈值汇总出来的：
    # - overall_acceptable_rate: overall_score >= 3
    # - crm_acceptable_rate: crm_business_usability_score >= 3
    # - task_acceptable_rate: task_execution_quality_score >= 3
    judged = [row["judge_result"] for row in case_results if isinstance(row.get("judge_result"), dict)]
    if not judged:
        return {
            "total_cases": len(case_results),
            "judged_cases": 0,
            "crm_field_correctness_avg": 0.0,
            "crm_business_usability_avg": 0.0,
            "task_structure_correctness_avg": 0.0,
            "task_execution_quality_avg": 0.0,
            "overall_score_avg": 0.0,
            "alignment_score_avg": 0.0,
            "overall_good_rate": 0.0,
            "overall_acceptable_rate": 0.0,
            "crm_acceptable_rate": 0.0,
            "task_acceptable_rate": 0.0,
        }

    def _avg(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    crm_field = [float(row["crm_writeback"]["field_correctness_score"]) for row in judged]
    crm_usable = [float(row["crm_writeback"]["business_usability_score"]) for row in judged]
    task_struct = [float(row["task_generation"]["structure_correctness_score"]) for row in judged]
    task_exec = [float(row["task_generation"]["execution_quality_score"]) for row in judged]
    overall = [float(row["overall"]["overall_score"]) for row in judged]
    alignment = [
        float(row["benchmark_alignment"]["alignment_score"])
        for row in judged
        if isinstance(row.get("benchmark_alignment"), dict) and "alignment_score" in row["benchmark_alignment"]
    ]

    return {
        "total_cases": len(case_results),
        "judged_cases": len(judged),
        "crm_field_correctness_avg": _avg(crm_field),
        "crm_business_usability_avg": _avg(crm_usable),
        "task_structure_correctness_avg": _avg(task_struct),
        "task_execution_quality_avg": _avg(task_exec),
        "overall_score_avg": _avg(overall),
        "alignment_score_avg": _avg(alignment),
        "overall_good_rate": sum(1 for score in overall if score >= 4.0) / len(overall),
        "overall_acceptable_rate": sum(1 for score in overall if score >= 3.0) / len(overall),
        "crm_acceptable_rate": sum(1 for score in crm_usable if score >= 3.0) / len(crm_usable),
        "task_acceptable_rate": sum(1 for score in task_exec if score >= 3.0) / len(task_exec),
    }


def _build_workflow_quality_report_markdown(bundle: dict[str, Any]) -> str:
    # workflow quality report 更接近“最终产品输出是否可用”的汇总视图。
    summary = bundle.get("summary", {})
    quality = summary.get("workflow_quality", {})
    lines = [
        "# Sales Copilot Workflow Quality Eval Report",
        "",
        "## Overview",
        "",
        f"- Dataset size: {summary.get('total_cases', 0)}",
        f"- Judged cases: {quality.get('judged_cases', 0)}",
        f"- With RAG: {bundle.get('with_rag', False)}",
        "",
        "## Quality Metrics",
        "",
        "| metric | value |",
        "| --- | --- |",
    ]
    for key in (
        "crm_field_correctness_avg",
        "crm_business_usability_avg",
        "task_structure_correctness_avg",
        "task_execution_quality_avg",
        "overall_score_avg",
        "alignment_score_avg",
        "overall_good_rate",
        "overall_acceptable_rate",
        "crm_acceptable_rate",
        "task_acceptable_rate",
    ):
        lines.append(f"| {key} | {quality.get(key, 'N/A')} |")

    lines.extend(["", "## Lowest-Scoring Cases", ""])
    ranked = [
        row
        for row in bundle.get("case_results", [])
        if isinstance(row.get("judge_result"), dict)
    ]
    ranked.sort(key=lambda row: float(row["judge_result"]["overall"]["overall_score"]))
    if not ranked:
        lines.append("- None")
    else:
        for row in ranked[:5]:
            lines.append(
                f"- {row.get('case_id', 'unknown')}: overall={row['judge_result']['overall']['overall_score']}, "
                f"summary={row['judge_result']['overall'].get('summary', '')}"
            )

    return "\n".join(lines) + "\n"


def write_workflow_quality_report_bundle(bundle: dict[str, Any], output_root: Path | str) -> str:
    # 和 parse/workflow 报告一样，每次单独落盘，方便比较 baseline / RAG / task-candidates 等方案。
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    report_dir = root / dt.datetime.now().strftime("%Y%m%d%H%M%S")
    report_dir.mkdir(parents=True, exist_ok=False)

    (report_dir / "report.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    (report_dir / "report.md").write_text(_build_workflow_quality_report_markdown(bundle), encoding="utf-8")
    with (report_dir / "case_results.jsonl").open("w", encoding="utf-8") as handle:
        for row in bundle.get("case_results", []):
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return str(report_dir)
