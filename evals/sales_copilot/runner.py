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
from sales_copilot.tools import seed_knowledge_chunks


_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "sales_copilot"


def _prepare_case_database(case_id: str, output_dir: Path) -> Path:
    database_dir = output_dir / "databases"
    database_dir.mkdir(parents=True, exist_ok=True)
    database_path = database_dir / f"{case_id}.db"
    if database_path.exists():
        database_path.unlink()
    return database_path


def _load_seed_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        chunks = payload.get("chunks", [])
        if isinstance(chunks, list):
            return chunks
    raise ValueError(f"Invalid seed data: {path}")


def _seed_case_database(database_path: Path) -> None:
    # 每个 case 都直接从仓库 seed 文件写入知识块，保证评测输入和计划一致。
    seed_knowledge_chunks(database_path, _load_seed_rows(_DATA_DIR / "seed_product_knowledge.json"))
    seed_knowledge_chunks(database_path, _load_seed_rows(_DATA_DIR / "seed_sales_playbook.json"))


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
    errors: list[str] = []
    parse_result: dict[str, Any] = {}
    workflow_result: dict[str, Any] = {}

    try:
        parse_result = _run_parse_step(case, llm_client=llm_client, database_path=database_path)
    except Exception as exc:
        errors.append(f"parse error: {exc}")

    if not errors:
        try:
            workflow_result = run_sales_copilot(
                customer_profile_text=case["customer_profile_text"],
                meeting_note_text=case["meeting_note_text"],
                database_path=database_path,
                llm_client=llm_client,
                meeting_summary=parse_result,
            )
        except Exception as exc:
            errors.append(f"workflow error: {exc}")

    return {
        "case_id": case["case_id"],
        "segment": case["segment"],
        "database_path": str(database_path),
        "expected_parse": case["expected_parse"],
        "expected_workflow": case["expected_workflow"],
        "parse_result": parse_result,
        "workflow_result": workflow_result,
        "parse_metrics": evaluate_parse_case(case, parse_result),
        "workflow_metrics": evaluate_workflow_case(case, workflow_result),
        "errors": errors,
        "error": "; ".join(errors),
    }


def run_offline_evaluation(cases_path, output_dir, llm_client) -> dict[str, Any]:
    cases_file = Path(cases_path)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    case_results = []
    for case in load_golden_cases(cases_file):
        case_results.append(_build_case_result(case, output_dir=output_root, llm_client=llm_client))
    return {
        "cases_path": str(cases_file),
        "output_dir": str(output_root),
        "summary": {
            "total_cases": len(case_results),
            "parse": summarize_parse_metrics([row["parse_metrics"] for row in case_results]),
            "workflow": summarize_workflow_metrics([row["workflow_metrics"] for row in case_results]),
        },
        "case_results": case_results,
    }
