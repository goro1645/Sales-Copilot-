from __future__ import annotations

from collections.abc import Iterable


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
    elif isinstance(value, Iterable):
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
        return text if text.isdigit() else "1"
    if isinstance(value, (list, tuple, set, dict)):
        return str(len(value))
    return "1"


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
