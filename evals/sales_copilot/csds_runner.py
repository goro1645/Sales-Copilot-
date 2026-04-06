from __future__ import annotations

from pathlib import Path
from typing import Any

from evals.sales_copilot.csds_adapter import CSDSCase, load_csds_cases, load_full_csds_cases
from evals.sales_copilot.metrics import evaluate_parse_case, summarize_parse_metrics
from sales_copilot.graph import parse_meeting_note_node


def _run_parse_step(case: CSDSCase, *, llm_client) -> dict[str, Any]:
    parse_state = parse_meeting_note_node(
        {
            "customer_profile_raw": case["customer_profile_text"],
            "meeting_note_raw": case["meeting_note_text"],
            "workflow_log": [],
        },
        llm_client=llm_client,
        database_path=None,
    )
    meeting_summary = parse_state.get("meeting_summary", {})
    if not isinstance(meeting_summary, dict):
        return {}
    return meeting_summary


def _build_case_result(case: CSDSCase, *, llm_client) -> dict[str, Any]:
    errors: list[str] = []
    parse_result: dict[str, Any] = {}
    try:
        parse_result = _run_parse_step(case, llm_client=llm_client)
    except Exception as exc:
        errors.append(f"parse error: {exc}")

    return {
        "case_id": case["case_id"],
        "segment": case["segment"],
        "source_dataset": case["source_dataset"],
        "source_uid": case["source_uid"],
        "source_split": case["source_split"],
        "source_note": case["source_note"],
        "expected_parse": case["expected_parse"],
        "expected_workflow": case["expected_workflow"],
        "parse_result": parse_result,
        "parse_metrics": evaluate_parse_case(case, parse_result),
        "errors": errors,
        "error": "; ".join(errors),
    }


def run_csds_parse_evaluation(cases_path, output_dir, llm_client) -> dict[str, Any]:
    cases_file = Path(cases_path)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    case_results = [_build_case_result(case, llm_client=llm_client) for case in load_csds_cases(cases_file)]
    return {
        "cases_path": str(cases_file),
        "output_dir": str(output_root),
        "dataset_kind": "csds",
        "report_kind": "parse_only",
        "summary": {
            "total_cases": len(case_results),
            "parse": summarize_parse_metrics([row["parse_metrics"] for row in case_results]),
        },
        "case_results": case_results,
    }


def run_full_csds_parse_evaluation(dataset_dir, output_dir, llm_client, *, splits: list[str] | None = None, limit: int | None = None) -> dict[str, Any]:
    dataset_root = Path(dataset_dir)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    case_results = [
        _build_case_result(case, llm_client=llm_client)
        for case in load_full_csds_cases(dataset_root, splits=splits, limit=limit)
    ]
    return {
        "cases_path": str(dataset_root),
        "output_dir": str(output_root),
        "dataset_kind": "full-csds",
        "report_kind": "parse_only",
        "summary": {
            "total_cases": len(case_results),
            "parse": summarize_parse_metrics([row["parse_metrics"] for row in case_results]),
        },
        "case_results": case_results,
    }
