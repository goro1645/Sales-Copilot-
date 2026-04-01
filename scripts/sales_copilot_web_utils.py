from __future__ import annotations

import html
from collections.abc import Iterable
from typing import Any


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

    tasks = result.get("task_payload") or (result.get("follow_up_plan") or {}).get("tasks") or []
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
