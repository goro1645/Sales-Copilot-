from __future__ import annotations

import html
import json
from collections.abc import Iterable
from typing import Any

from sales_copilot.stream_cli import render_stream_event


STREAM_PROGRESS_STEPS: list[tuple[str, str]] = [
    ("context", "Context"),
    ("parse", "Parse"),
    ("retrieve", "Retrieve"),
    ("score", "Score"),
    ("plan", "Plan"),
    ("finalize", "Finalize"),
]

NODE_TO_PROGRESS_STAGE = {
    "ingest_files": "context",
    "load_account_memory": "context",
    "parse_meeting_note": "parse",
    "retrieve_context": "retrieve",
    "evaluate_lead": "score",
    "build_task_candidates": "plan",
    "standard_follow_up": "plan",
    "high_priority_follow_up": "plan",
    "need_more_info": "plan",
    "low_priority_nurture": "plan",
    "write_back_crm": "finalize",
    "generate_dashboard_output": "finalize",
}

STAGE_DESCRIPTIONS = {
    "context": "Preparing customer context and workspace state.",
    "parse": "Extracting structured facts from the meeting notes.",
    "retrieve": "Looking up supporting knowledge and account history.",
    "score": "Scoring opportunity priority, stage, and risks.",
    "plan": "Building next steps, CRM updates, and task candidates.",
    "finalize": "Writing outputs back and assembling the dashboard.",
}


def _copy_progress_state(progress_state: dict[str, Any]) -> dict[str, Any]:
    copied = dict(progress_state)
    copied["completed_stages"] = list(progress_state.get("completed_stages", []))
    return copied


def _stage_label(stage: str) -> str:
    for key, label in STREAM_PROGRESS_STEPS:
        if key == stage:
            return label
    return "Workflow"


def _summarize_state_patch(node: str, patch: dict[str, Any]) -> str:
    if node == "retrieve_context":
        doc_count = patch.get("retrieved_doc_count")
        if doc_count is None:
            docs = patch.get("retrieved_docs")
            doc_count = len(docs) if isinstance(docs, list) else 0
        return f"Found {doc_count} supporting document(s)."
    if node == "evaluate_lead":
        priority = _normalize_text(patch.get("lead_priority"), "unknown")
        stage = _normalize_text(patch.get("opportunity_stage"), "unknown")
        return f"Priority {priority}, stage {stage}."
    if node == "build_task_candidates":
        candidates = patch.get("task_candidates") or []
        count = len(candidates) if isinstance(candidates, list) else 0
        return f"Prepared {count} task candidate(s)."
    if node in {"standard_follow_up", "high_priority_follow_up", "need_more_info", "low_priority_nurture"}:
        task_payload = patch.get("task_payload") or []
        count = len(task_payload) if isinstance(task_payload, list) else 0
        return f"Drafted {count} follow-up task(s)."
    if node == "write_back_crm":
        crm_ids = patch.get("crm_update_ids") or []
        count = len(crm_ids) if isinstance(crm_ids, list) else 0
        return f"Prepared {count} CRM update(s)."
    if node == "generate_dashboard_output":
        return "Final dashboard output is ready."
    return STAGE_DESCRIPTIONS.get(NODE_TO_PROGRESS_STAGE.get(node, ""), "Processing workflow data.")


def escape_html_text(value: Any) -> str:
    """把会进 HTML 的内容先转义，避免页面把用户输入当成标签。"""

    return html.escape("" if value is None else str(value), quote=True)


def _first_present(*values):
    """返回第一个真正有内容的值，方便界面兜底展示。"""

    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _format_text(value, default: str = "N/A") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        text = value.strip()
        return text or default
    return str(value)


def _format_list_text(value, default: str = "None") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        text = value.strip()
        return text or default
    if isinstance(value, dict):
        items = list(value.values())
    elif isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        items = list(value)
    else:
        items = [value]

    cleaned = [str(item).strip() for item in items if str(item).strip()]
    return ", ".join(cleaned) if cleaned else default


def _format_count(value) -> str:
    if value is None:
        return "0"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        text = value.strip()
        return text if text.isdigit() else "0"
    if isinstance(value, (list, tuple, set, dict)):
        return str(len(value))
    return "0"


def build_card_html(label: str, value: str, note: str = "") -> str:
    """把卡片文案拼成 HTML，动态值先转义，页面才能安全渲染。"""

    return (
        '<div class="card-shell">'
        f'<div class="card-label">{escape_html_text(label)}</div>'
        f'<div class="card-value">{escape_html_text(value)}</div>'
        f'<div class="card-note">{escape_html_text(note)}</div>'
        "</div>"
    )


def build_summary_html(summary: str) -> str:
    """把摘要包成安全的 HTML 片段。"""

    return f'<div class="subtle-copy">{escape_html_text(summary)}</div>'


def _normalize_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip() or default
    return str(value)


def _normalize_list_like(value: Any, *, default: list[str] | None = None) -> list[str]:
    if default is None:
        default = []
    if value is None:
        return list(default)
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else list(default)
    if isinstance(value, dict):
        values = list(value.values())
    elif isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        values = list(value)
    else:
        values = [value]

    cleaned = []
    for item in values:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            cleaned.append(text)
    return cleaned or list(default)


def _normalize_context_item(item: Any, index: int) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    matched_terms = _normalize_list_like(item.get("matched_terms"))
    return {
        "Rank": index,
        "Source": _normalize_text(item.get("source_name") or item.get("source_type"), "Context"),
        "Score": item.get("score", ""),
        "Matched Terms": ", ".join(matched_terms) if matched_terms else "None",
        "Snippet": _normalize_text(item.get("chunk_text") or item.get("text") or item.get("description"), "")[:220],
    }


def normalize_context_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    """把检索结果整理成表格行，脏数据也要尽量能显示。"""

    rows: list[dict[str, Any]] = []
    for index, item in enumerate(result.get("retrieved_docs") or [], start=1):
        normalized = _normalize_context_item(item, index)
        if normalized is not None:
            rows.append(normalized)
    return rows


def _normalize_task_item(item: Any, index: int) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    return {
        "Rank": index,
        "Title": _normalize_text(item.get("title"), "Follow up"),
        "Priority": _normalize_text(item.get("priority"), "medium"),
        "Owner": _normalize_text(item.get("owner"), "Sales"),
        "Due": _normalize_text(item.get("due_at") or item.get("due"), ""),
        "Status": _normalize_text(item.get("status"), "open"),
    }


def normalize_task_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    """把任务列表整理成表格行，非字典项直接跳过。"""

    tasks = result.get("task_payload")
    if not tasks:
        follow_up_plan = result.get("follow_up_plan")
        if isinstance(follow_up_plan, dict):
            tasks = follow_up_plan.get("tasks")
        else:
            tasks = []
    tasks = tasks or []
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(tasks, start=1):
        normalized = _normalize_task_item(item, index)
        if normalized is not None:
            rows.append(normalized)
    return rows


def clear_run_result_state(session_state: dict[str, Any], error_message: str) -> None:
    """失败时同时清空旧结果，避免页面还显示上一次成功的数据。"""

    session_state["last_result"] = None
    session_state["last_error"] = error_message


def default_stream_progress_state() -> dict[str, Any]:
    return {
        "status": "idle",
        "current_stage": "",
        "current_node": "",
        "completed_stages": [],
        "headline": "Ready to run",
        "detail": "Run the copilot to watch stage-by-stage progress.",
        "error_message": "",
    }


def apply_stream_event_to_progress_state(progress_state: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    state = _copy_progress_state(progress_state)
    event_type = _normalize_text(event.get("type"), "")
    node = _normalize_text(event.get("node"), "")
    stage = NODE_TO_PROGRESS_STAGE.get(node, state.get("current_stage", ""))

    if event_type == "workflow_started":
        state["status"] = "running"
        state["headline"] = "Starting workflow"
        state["detail"] = "Preparing customer context and workflow state."
        state["error_message"] = ""
        return state

    if event_type == "node_started":
        state["status"] = "running"
        state["current_stage"] = stage
        state["current_node"] = node
        state["headline"] = f"{_stage_label(stage)} in progress"
        state["detail"] = STAGE_DESCRIPTIONS.get(stage, "Processing workflow data.")
        return state

    if event_type == "state_patch":
        if stage:
            state["current_stage"] = stage
        state["current_node"] = node or state.get("current_node", "")
        state["detail"] = _summarize_state_patch(node, event.get("patch") or {})
        return state

    if event_type == "node_finished":
        if stage and stage not in state["completed_stages"]:
            state["completed_stages"].append(stage)
        state["current_stage"] = stage or state.get("current_stage", "")
        state["current_node"] = node
        state["headline"] = f"{_stage_label(stage)} complete" if stage else "Step complete"
        state["detail"] = _summarize_state_patch(node, {})
        return state

    if event_type == "workflow_finished":
        state["status"] = "completed"
        state["headline"] = "Workflow complete"
        state["detail"] = "Dashboard, CRM preview, and tasks are ready."
        state["current_stage"] = "finalize"
        for stage_key, _label in STREAM_PROGRESS_STEPS:
            if stage_key not in state["completed_stages"]:
                state["completed_stages"].append(stage_key)
        return state

    if event_type == "error":
        state["status"] = "failed"
        state["headline"] = "Run failed"
        state["error_message"] = _normalize_text(event.get("message"), "Workflow failed.")
        state["detail"] = state["error_message"]
        return state

    return state


def build_progress_panel_html(progress_state: dict[str, Any]) -> str:
    status = _normalize_text(progress_state.get("status"), "idle")
    completed = set(_normalize_list_like(progress_state.get("completed_stages")))
    current_stage = _normalize_text(progress_state.get("current_stage"), "")

    if status == "completed":
        status_label = "Completed"
        status_class = "status-complete"
    elif status == "failed":
        status_label = "Failed"
        status_class = "status-failed"
    elif status == "running":
        status_label = "Running"
        status_class = "status-running"
    else:
        status_label = "Idle"
        status_class = "status-idle"

    step_html = []
    for stage_key, label in STREAM_PROGRESS_STEPS:
        if status == "completed" or stage_key in completed:
            step_class = "progress-step is-complete"
        elif stage_key == current_stage and status == "running":
            step_class = "progress-step is-current"
        else:
            step_class = "progress-step"
        step_html.append(f'<span class="{step_class}">{escape_html_text(label)}</span>')

    error_message = _normalize_text(progress_state.get("error_message"), "")
    if error_message:
        detail_html = f'<div class="progress-error">{escape_html_text(error_message)}</div>'
    else:
        detail_html = f'<div class="progress-detail">{escape_html_text(_normalize_text(progress_state.get("detail"), ""))}</div>'

    return (
        '<div class="progress-shell">'
        f'<div class="progress-status-row"><span class="progress-status-pill {status_class}">{escape_html_text(status_label)}</span>'
        f'<span class="progress-headline">{escape_html_text(_normalize_text(progress_state.get("headline"), "Workflow progress"))}</span></div>'
        f'<div class="progress-steps">{"".join(step_html)}</div>'
        f"{detail_html}"
        "</div>"
    )


def build_stream_api_payload(
    *,
    customer_profile_text: str,
    meeting_note_text: str,
    database_path: str,
    execution_mode: str,
    api_key: str,
    api_base_url: str,
    api_model: str,
) -> dict[str, Any]:
    return {
        "customer_profile_text": customer_profile_text,
        "meeting_note_text": meeting_note_text,
        "database_path": database_path,
        "execution_mode": execution_mode,
        "api_key": api_key,
        "api_base_url": api_base_url,
        "api_model": api_model,
    }


def parse_sse_event_block(block: str) -> dict[str, Any] | None:
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    data_line = next((line for line in lines if line.startswith("data:")), None)
    if data_line is None:
        return None
    payload = data_line[len("data:") :].strip()
    if not payload:
        return None
    return json.loads(payload)


def append_stream_log_line(log_text: str, event: dict[str, Any]) -> str:
    line = render_stream_event(event)
    if not line:
        return log_text
    if not log_text:
        return line
    return f"{log_text}\n{line}"


def build_dashboard_cards(result: dict) -> dict[str, str]:
    """把 runner 返回值整理成适合仪表盘展示的卡片文案。"""

    dashboard_output = result.get("dashboard_output") if isinstance(result.get("dashboard_output"), dict) else {}
    customer_profile_structured = (
        result.get("customer_profile_structured") if isinstance(result.get("customer_profile_structured"), dict) else {}
    )

    account_name = _first_present(
        dashboard_output.get("account_name"),
        result.get("account_name"),
        customer_profile_structured.get("account_name"),
    )
    lead_score = _first_present(result.get("lead_score"), dashboard_output.get("lead_score"))
    lead_priority = _first_present(result.get("lead_priority"), dashboard_output.get("lead_priority"))
    opportunity_stage = _first_present(result.get("opportunity_stage"), dashboard_output.get("opportunity_stage"))
    risk_flags = _first_present(result.get("risk_flags"), dashboard_output.get("risk_flags"))

    retrieved_docs = _first_present(
        dashboard_output.get("retrieved_doc_count"),
        result.get("retrieved_doc_count"),
        result.get("retrieved_docs"),
    )
    crm_updates = _first_present(
        dashboard_output.get("crm_update_ids"),
        result.get("crm_update_ids"),
    )
    task_payload = _first_present(
        dashboard_output.get("task_payload"),
        result.get("task_payload"),
    )

    return {
        "Account": _format_text(account_name),
        "Lead Score": _format_text(lead_score),
        "Priority": _format_text(lead_priority),
        "Stage": _format_text(opportunity_stage),
        "Risk Flags": _format_list_text(risk_flags),
        "Retrieved Docs": _format_count(retrieved_docs),
        "CRM Updates": _format_count(crm_updates),
        "Tasks": _format_count(task_payload),
    }
