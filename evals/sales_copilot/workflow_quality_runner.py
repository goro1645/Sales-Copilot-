from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

from evals.sales_copilot.runner import _prepare_case_database, _run_parse_step, _seed_case_database
from evals.sales_copilot.workflow_calibrated_benchmark import load_jsonl_rows
from evals.sales_copilot.workflow_quality_judge import WorkflowQualityJudge
from sales_copilot.runner import run_sales_copilot
from sales_copilot.storage import list_crm_updates, list_tasks


def normalize_actual_crm_writeback(workflow_result: dict[str, Any], *, database_path: Path | str | None = None) -> dict[str, Any]:
    crm_updates = list_crm_updates(database_path) if database_path else []
    latest_after: dict[str, Any] = {}
    if crm_updates:
        last_row = crm_updates[-1]
        try:
            latest_after = json.loads(str(last_row.get("after_json", "{}")))
        except json.JSONDecodeError:
            latest_after = {}

    follow_up_plan = workflow_result.get("follow_up_plan", {})
    if not isinstance(follow_up_plan, dict):
        follow_up_plan = {}

    return {
        "crm_writeback_performed": bool(workflow_result.get("crm_writeback_performed", False)),
        "crm_update_ids": list(workflow_result.get("crm_update_ids", []) or []),
        "lead_priority": str(workflow_result.get("lead_priority", "")).strip(),
        "opportunity_stage": str(workflow_result.get("opportunity_stage", "")).strip(),
        "risk_flags": [str(item).strip() for item in workflow_result.get("risk_flags", []) or [] if str(item).strip()],
        "follow_up_summary": str(follow_up_plan.get("summary", "")).strip(),
        "account_status": str(latest_after.get("status", "")).strip(),
        "recommended_next_step": str(latest_after.get("recommended_next_step", "")).strip(),
        "crm_after": latest_after,
    }


def normalize_actual_generated_tasks(workflow_result: dict[str, Any], *, database_path: Path | str | None = None) -> list[dict[str, Any]]:
    task_rows = workflow_result.get("task_payload", [])
    if not isinstance(task_rows, list) or not task_rows:
        task_rows = list_tasks(database_path) if database_path else []

    normalized: list[dict[str, Any]] = []
    for task in task_rows:
        if not isinstance(task, dict):
            continue
        normalized.append(
            {
                "title": str(task.get("title", "")).strip(),
                "description": str(task.get("description", "")).strip(),
                "priority": str(task.get("priority", "")).strip(),
                "owner": str(task.get("owner", "")).strip(),
                "timing_or_due_hint": str(task.get("due_at", task.get("timing", ""))).strip(),
            }
        )
    return normalized


@contextmanager
def _rag_override(*, with_rag: bool):
    if with_rag:
        yield
        return
    with (
        patch("sales_copilot.graph.hybrid_retrieve_knowledge_chunks", return_value=[]),
        patch("sales_copilot.graph.search_account_history", return_value=[]),
    ):
        yield


def build_workflow_quality_case_result(
    case: dict[str, Any],
    *,
    output_dir: Path,
    workflow_llm_client,
    judge: WorkflowQualityJudge,
    execution_mode: str,
    with_rag: bool,
) -> dict[str, Any]:
    database_path = _prepare_case_database(str(case["case_id"]), output_dir)
    _seed_case_database(database_path)
    workflow_errors: list[str] = []
    judge_errors: list[str] = []
    parse_result: dict[str, Any] = {}
    workflow_result: dict[str, Any] = {}
    actual_crm_writeback: dict[str, Any] = {}
    actual_generated_tasks: list[dict[str, Any]] = []
    judge_result: dict[str, Any] | None = None

    try:
        parse_result = _run_parse_step(case, llm_client=workflow_llm_client, database_path=database_path)
    except Exception as exc:
        workflow_errors.append(f"parse error: {exc}")

    if not workflow_errors:
        try:
            with _rag_override(with_rag=with_rag):
                workflow_result = run_sales_copilot(
                    customer_profile_text=str(case.get("customer_profile_text", "")),
                    meeting_note_text=str(case.get("meeting_note_text", "")),
                    database_path=database_path,
                    llm_client=workflow_llm_client,
                    meeting_summary=parse_result,
                    meeting_summary_provided=True,
                    execution_mode=execution_mode,
                )
        except Exception as exc:
            workflow_errors.append(f"workflow error: {exc}")

    if not workflow_errors:
        actual_crm_writeback = normalize_actual_crm_writeback(workflow_result, database_path=database_path)
        actual_generated_tasks = normalize_actual_generated_tasks(workflow_result, database_path=database_path)
        try:
            stage1_result, stage2_result = judge.evaluate_case(
                case_id=str(case.get("case_id", "")),
                meeting_note_text=str(case.get("meeting_note_text", "")),
                actual_crm_writeback=actual_crm_writeback,
                actual_generated_tasks=actual_generated_tasks,
                expected_workflow=dict(case.get("expected_workflow", {})),
                customer_profile_text=str(case.get("customer_profile_text", "")),
            )
            judge_result = {**stage1_result, **stage2_result}
        except Exception as exc:
            judge_errors.append(f"judge error: {exc}")

    return {
        "case_id": case.get("case_id"),
        "source_case_id": case.get("source_case_id"),
        "segment": case.get("segment"),
        "workflow_sampling_bucket": case.get("workflow_sampling_bucket", ""),
        "with_rag": with_rag,
        "expected_workflow": case.get("expected_workflow", {}),
        "parse_result": parse_result,
        "workflow_result": workflow_result,
        "actual_crm_writeback": actual_crm_writeback,
        "actual_generated_tasks": actual_generated_tasks,
        "judge_result": judge_result,
        "workflow_errors": workflow_errors,
        "judge_errors": judge_errors,
        "error": "; ".join([*workflow_errors, *judge_errors]),
    }


def run_workflow_quality_evaluation(
    *,
    cases_path: Path | str,
    output_dir: Path | str,
    workflow_llm_client,
    judge_llm_client,
    execution_mode: str = "direct",
    with_rag: bool = False,
) -> dict[str, Any]:
    cases_file = Path(cases_path)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    judge = WorkflowQualityJudge(judge_llm_client)
    case_results: list[dict[str, Any]] = []
    for case in load_jsonl_rows(cases_file):
        case_results.append(
            build_workflow_quality_case_result(
                case,
                output_dir=output_root,
                workflow_llm_client=workflow_llm_client,
                judge=judge,
                execution_mode=execution_mode,
                with_rag=with_rag,
            )
        )
    return {
        "cases_path": str(cases_file),
        "output_dir": str(output_root),
        "execution_mode": execution_mode,
        "with_rag": with_rag,
        "summary": {"total_cases": len(case_results)},
        "case_results": case_results,
    }
