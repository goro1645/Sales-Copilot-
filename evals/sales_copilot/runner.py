from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evals.sales_copilot.cases import GoldenCase, load_golden_cases
from evals.sales_copilot.metrics import (
    evaluate_parse_case,
    evaluate_workflow_case,
    summarize_parse_metrics,
    summarize_workflow_metrics,
)
from sales_copilot.graph import parse_meeting_note_node
from sales_copilot.runner import run_sales_copilot
from sales_copilot.tools import sample_playbook_chunks, sample_product_chunks, seed_knowledge_chunks


def _prepare_case_database(case_id: str, output_dir: Path) -> Path:
    database_dir = output_dir / "databases"
    database_dir.mkdir(parents=True, exist_ok=True)
    database_path = database_dir / f"{case_id}.db"
    if database_path.exists():
        database_path.unlink()
    return database_path


def _seed_case_database(database_path: Path) -> None:
    # 每个 case 用独立库，并在跑流程前写入两份固定知识库，避免串库和脏状态。
    seed_knowledge_chunks(database_path, sample_product_chunks())
    seed_knowledge_chunks(database_path, sample_playbook_chunks())


def _run_parse_step(case: GoldenCase, *, llm_client, database_path: Path) -> dict[str, Any]:
    parse_state = parse_meeting_note_node(
        {
            "customer_profile_raw": case["customer_profile_text"],
            "meeting_note_raw": case["meeting_note_text"],
            "workflow_log": [],
        },
        llm_client=llm_client,
        database_path=database_path,
    )
    meeting_summary = parse_state.get("meeting_summary", {})
    if not isinstance(meeting_summary, dict):
        return {}
    return meeting_summary


def _build_case_result(case: GoldenCase, *, output_dir: Path, llm_client) -> dict[str, Any]:
    database_path = _prepare_case_database(case["case_id"], output_dir)
    _seed_case_database(database_path)

    parse_result = _run_parse_step(case, llm_client=llm_client, database_path=database_path)
    workflow_result = run_sales_copilot(
        customer_profile_text=case["customer_profile_text"],
        meeting_note_text=case["meeting_note_text"],
        database_path=database_path,
        llm_client=llm_client,
    )
    parse_metrics = evaluate_parse_case(case, parse_result)
    workflow_metrics = evaluate_workflow_case(case, workflow_result)
    return {
        "case_id": case["case_id"],
        "segment": case["segment"],
        "database_path": str(database_path),
        "expected_parse": case["expected_parse"],
        "expected_workflow": case["expected_workflow"],
        "parse_result": parse_result,
        "workflow_result": workflow_result,
        "parse_metrics": parse_metrics,
        "workflow_metrics": workflow_metrics,
    }


def run_offline_evaluation(cases_path, output_dir, llm_client) -> dict[str, Any]:
    cases_file = Path(cases_path)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    case_results = [
        _build_case_result(case, output_dir=output_root, llm_client=llm_client)
        for case in load_golden_cases(cases_file)
    ]
    parse_rows = [row["parse_metrics"] for row in case_results]
    workflow_rows = [row["workflow_metrics"] for row in case_results]
    return {
        "cases_path": str(cases_file),
        "output_dir": str(output_root),
        "summary": {
            "total_cases": len(case_results),
            "parse_summary": summarize_parse_metrics(parse_rows),
            "workflow_summary": summarize_workflow_metrics(workflow_rows),
        },
        "case_results": case_results,
    }
