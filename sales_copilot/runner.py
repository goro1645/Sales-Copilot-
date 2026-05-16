"""Workflow entrypoints for running Sales Copilot end-to-end.

Read this file when you want the shortest path from input to output:
- `run_sales_copilot(...)` returns the final workflow result.
- `run_sales_copilot_stream(...)` emits structured events for CLI, SSE, and UI.

The business rules still live in `graph.py`. This file mainly wraps those nodes
into either a final result or a stream of node/token events.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sales_copilot.graph import (
    _augment_follow_up_payload_with_missing_facts,
    _coerce_lead_score,
    _first_payload_value,
    _normalize_list,
    _parse_json_object,
    _step_result,
    _unwrap_payload_object,
    build_sales_copilot_graph,
    build_task_candidates_node,
    generate_dashboard_output_node,
    ingest_files_node,
    load_account_memory_node,
    low_priority_nurture_node,
    need_more_info_node,
    retrieve_context_node,
    route_after_lead_evaluation,
    write_back_crm_node,
)
from sales_copilot.prompts import (
    build_followup_plan_messages,
    build_lead_scoring_messages,
    build_meeting_parse_messages,
)
from sales_copilot.retrieval import load_default_embedder
from sales_copilot.streaming import (
    make_error_event,
    make_node_finished_event,
    make_node_started_event,
    make_state_patch_event,
    make_workflow_finished_event,
    make_workflow_started_event,
    stream_llm_completion,
)
from sales_copilot.task_candidates import build_tasks_from_candidates


def run_sales_copilot(
    *,
    customer_profile_text: str,
    meeting_note_text: str,
    database_path: Path | str,
    llm_client,
    account_id: int | None = None,
    meeting_summary: dict[str, Any] | None = None,
    meeting_summary_provided: bool = False,
    execution_mode: str = "direct",
    mcp_client=None,
) -> dict[str, Any]:
    # 非流式入口：适合离线评测、脚本调用和“只关心最终结果”的场景。
    # 这里仅整理图所需状态；评测已拿到 parse 结果时可直接复用，避免重复请求模型。
    if execution_mode not in {"direct", "mcp"}:
        raise ValueError("execution_mode must be one of: direct, mcp")
    if execution_mode == "mcp" and mcp_client is None:
        raise ValueError("mcp mode requires an mcp_client")

    graph = build_sales_copilot_graph(
        llm_client=llm_client,
        database_path=database_path,
        mcp_client=mcp_client,
        retrieval_embedder=load_default_embedder(),
    )
    state: dict[str, Any] = {
        "customer_profile_raw": customer_profile_text,
        "meeting_note_raw": meeting_note_text,
        "workflow_log": [],
        "execution_mode": execution_mode,
    }
    if account_id is not None:
        state["account_id"] = account_id
    if meeting_summary is not None:
        state["meeting_summary"] = dict(meeting_summary)
    if meeting_summary_provided:
        state["meeting_summary_provided"] = True
    return graph.invoke(state)


def _build_initial_state(
    *,
    customer_profile_text: str,
    meeting_note_text: str,
    execution_mode: str,
    account_id: int | None,
    meeting_summary: dict[str, Any] | None,
    meeting_summary_provided: bool,
) -> dict[str, Any]:
    # 这里把 workflow 的最小输入骨架固定住。
    # 后续节点会不断把真实业务结果填回这个共享 state。
    state: dict[str, Any] = {
        "customer_profile_raw": customer_profile_text,
        "meeting_note_raw": meeting_note_text,
        "workflow_log": [],
        "execution_mode": execution_mode,
    }
    if account_id is not None:
        state["account_id"] = account_id
    if meeting_summary is not None:
        state["meeting_summary"] = dict(meeting_summary)
    if meeting_summary_provided:
        state["meeting_summary_provided"] = True
    return state


def _apply_patch(state: dict[str, Any], patch: dict[str, Any]) -> None:
    state.update(patch)


def _run_sync_node(state: dict[str, Any], node_name: str, fn, **kwargs):
    # 对非 LLM 节点统一封装 started -> patch -> finished 事件。
    yield make_node_started_event(node_name, streaming=False)
    patch = fn(state, **kwargs)
    _apply_patch(state, patch)
    yield make_state_patch_event(node_name, patch)
    yield make_node_finished_event(node_name)


def _run_parse_node(state: dict[str, Any], llm_client):
    node_name = "parse_meeting_note"
    # `meeting_summary` 是整个 workflow 的事实底座：
    # - confirmed_needs: 客户明确提出的需求/问题
    # - next_steps: 接下来要执行的动作
    # - timeline_signals: 时间承诺、截止时间、等待窗口
    existing_summary = state.get("meeting_summary")
    if state.get("meeting_summary_provided") or (
        isinstance(existing_summary, dict) and existing_summary and not state.get("meeting_note_raw")
    ):
        yield make_node_started_event(node_name, streaming=False)
        patch = _step_result(state, node_name, {"meeting_summary": existing_summary})
        _apply_patch(state, patch)
        yield make_state_patch_event(node_name, patch)
        yield make_node_finished_event(node_name)
        return

    messages = build_meeting_parse_messages(
        customer_profile_text=state.get("customer_profile_raw", ""),
        meeting_note_text=state.get("meeting_note_raw", ""),
    )
    yield make_node_started_event(node_name, streaming=True)
    content = yield from stream_llm_completion(
        llm_client=llm_client,
        node=node_name,
        messages=messages,
        response_format={"type": "json_object"},
    )
    payload = _parse_json_object(content)
    patch = _step_result(state, node_name, {"meeting_summary": payload})
    _apply_patch(state, patch)
    yield make_state_patch_event(node_name, patch)
    yield make_node_finished_event(node_name)


def _run_evaluate_lead_node(state: dict[str, Any], llm_client):
    node_name = "evaluate_lead"
    # lead 评估阶段主要由模型直接给出 score / priority / stage / risks。
    # 规则层只做轻量兜底，不手工“算分”。
    if (
        state.get("lead_score") is not None
        and not state.get("customer_profile_raw")
        and not state.get("meeting_note_raw")
        and state.get("meeting_summary")
    ):
        yield make_node_started_event(node_name, streaming=False)
        patch = _step_result(
            state,
            node_name,
            {
                "lead_score": state.get("lead_score", 0),
                "lead_priority": state.get("lead_priority", "medium"),
                "opportunity_stage": state.get("opportunity_stage", "discovery"),
                "risk_flags": list(state.get("risk_flags", [])),
            },
        )
        _apply_patch(state, patch)
        yield make_state_patch_event(node_name, patch)
        yield make_node_finished_event(node_name)
        return

    messages = build_lead_scoring_messages(
        customer_profile_text=state.get("customer_profile_raw", ""),
        meeting_summary=state.get("meeting_summary", {}),
        retrieved_docs=state.get("retrieved_docs", []),
        account_memory=state.get("account_memory", {}),
    )
    yield make_node_started_event(node_name, streaming=True)
    content = yield from stream_llm_completion(
        llm_client=llm_client,
        node=node_name,
        messages=messages,
        response_format={"type": "json_object"},
    )
    payload = _unwrap_payload_object(_parse_json_object(content))
    lead_score = _coerce_lead_score(_first_payload_value(payload, "lead_score", "score"))
    lead_priority = str(
        _first_payload_value(payload, "lead_priority", "priority")
        or ("high" if lead_score and lead_score >= 80 else "medium")
    )
    opportunity_stage = str(_first_payload_value(payload, "opportunity_stage", "stage") or "discovery")
    risk_flags = _normalize_list(_first_payload_value(payload, "risk_flags", "risks", "risk_labels"))
    patch = _step_result(
        state,
        node_name,
        {
            "lead_score": lead_score if lead_score is not None else 0,
            "lead_priority": lead_priority,
            "opportunity_stage": opportunity_stage,
            "risk_flags": risk_flags,
        },
    )
    _apply_patch(state, patch)
    yield make_state_patch_event(node_name, patch)
    yield make_node_finished_event(node_name)


def _run_followup_node(state: dict[str, Any], llm_client, node_name: str):
    # follow-up / task 生成时会显式喂入 `task_candidates`，避免任务退化成泛模板。
    messages = build_followup_plan_messages(
        meeting_summary=state.get("meeting_summary", {}),
        opportunity_stage=state.get("opportunity_stage", ""),
        risk_flags=_normalize_list(state.get("risk_flags")),
        task_candidates=list(state.get("task_candidates", [])),
    )
    yield make_node_started_event(node_name, streaming=True)
    content = yield from stream_llm_completion(
        llm_client=llm_client,
        node=node_name,
        messages=messages,
        response_format={"type": "json_object"},
    )
    payload = _parse_json_object(content)
    tasks = payload.get("tasks") or payload.get("task_payload") or []
    payload["tasks"] = tasks if isinstance(tasks, list) else []
    # `task_candidates` 是程序构造的中间层，不是另一轮自由生成。
    candidate_tasks = build_tasks_from_candidates(list(state.get("task_candidates", [])))
    existing_tasks = payload.get("tasks", [])
    merged_tasks = []
    seen = set()
    for task in list(existing_tasks) + candidate_tasks:
        if not isinstance(task, dict):
            continue
        title = str(task.get("title", "")).strip()
        due_at = str(task.get("due_at", "")).strip()
        key = (title.lower(), due_at)
        if not title or key in seen:
            continue
        seen.add(key)
        merged_tasks.append(task)
    payload["tasks"] = merged_tasks
    if not str(payload.get("summary", "")).strip() and state.get("task_candidates"):
        payload["summary"] = "; ".join(
            str(row.get("text", "")).strip()
            for row in list(state.get("task_candidates", []))[:2]
            if str(row.get("text", "")).strip()
        )
    payload = _augment_follow_up_payload_with_missing_facts(state, payload)
    patch = _step_result(state, node_name, {"follow_up_plan": payload, "task_payload": list(payload.get("tasks", []))})
    _apply_patch(state, patch)
    yield make_state_patch_event(node_name, patch)
    yield make_node_finished_event(node_name)


def run_sales_copilot_stream(
    *,
    customer_profile_text: str,
    meeting_note_text: str,
    database_path: Path | str,
    llm_client,
    account_id: int | None = None,
    meeting_summary: dict[str, Any] | None = None,
    meeting_summary_provided: bool = False,
    execution_mode: str = "direct",
    mcp_client=None,
):
    # 流式入口与非流式入口共用同一套业务节点，只是把中间过程包装成结构化事件流。
    if execution_mode not in {"direct", "mcp"}:
        raise ValueError("execution_mode must be one of: direct, mcp")
    if execution_mode == "mcp" and mcp_client is None:
        raise ValueError("mcp mode requires an mcp_client")

    retrieval_embedder = load_default_embedder()
    state = _build_initial_state(
        customer_profile_text=customer_profile_text,
        meeting_note_text=meeting_note_text,
        execution_mode=execution_mode,
        account_id=account_id,
        meeting_summary=meeting_summary,
        meeting_summary_provided=meeting_summary_provided,
    )

    yield make_workflow_started_event("sales_copilot", execution_mode)

    try:
        yield from _run_sync_node(state, "ingest_files", ingest_files_node, llm_client=llm_client, database_path=database_path)
        yield from _run_parse_node(state, llm_client)
        yield from _run_sync_node(
            state,
            "retrieve_context",
            retrieve_context_node,
            llm_client=llm_client,
            database_path=database_path,
            retrieval_embedder=retrieval_embedder,
        )
        yield from _run_sync_node(state, "load_account_memory", load_account_memory_node, llm_client=llm_client, database_path=database_path)
        yield from _run_evaluate_lead_node(state, llm_client)
        yield from _run_sync_node(state, "build_task_candidates", build_task_candidates_node, llm_client=llm_client, database_path=database_path)

        # route 是执行分流，不等于 opportunity_stage。
        route = route_after_lead_evaluation(state)
        if route == "need_more_info":
            yield from _run_sync_node(state, "need_more_info", need_more_info_node, llm_client=llm_client, database_path=database_path)
        elif route == "low_priority_nurture":
            yield from _run_sync_node(
                state,
                "low_priority_nurture",
                low_priority_nurture_node,
                llm_client=llm_client,
                database_path=database_path,
            )
        elif route == "standard_follow_up":
            yield from _run_followup_node(state, llm_client, "standard_follow_up")
        else:
            yield from _run_followup_node(state, llm_client, "high_priority_follow_up")

        yield from _run_sync_node(
            state,
            "write_back_crm",
            write_back_crm_node,
            llm_client=llm_client,
            database_path=database_path,
            mcp_client=mcp_client,
        )
        yield from _run_sync_node(
            state,
            "generate_dashboard_output",
            generate_dashboard_output_node,
            llm_client=llm_client,
            database_path=database_path,
        )
    except Exception as exc:
        yield make_error_event("sales_copilot", str(exc))
        raise

    yield make_workflow_finished_event(state)
