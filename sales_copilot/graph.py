from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from langgraph.graph import END, StateGraph

from sales_copilot.state import SalesCopilotState


def _append_workflow_log(state: SalesCopilotState, step_name: str) -> dict[str, Any]:
    # 占位节点只负责记录流程走到哪一步，方便后续把真实业务逻辑接进来。
    workflow_log = list(state.get("workflow_log", []))
    workflow_log.append(step_name)
    return {"workflow_log": workflow_log}


def _stub_node(step_name: str) -> Callable[[SalesCopilotState], dict[str, Any]]:
    def _node(state: SalesCopilotState) -> dict[str, Any]:
        return _append_workflow_log(state, step_name)

    return _node


def _coerce_lead_score(raw_lead_score: Any) -> int | None:
    try:
        return int(raw_lead_score)
    except (TypeError, ValueError):
        return None


def route_after_lead_evaluation(state: SalesCopilotState) -> str:
    meeting_summary = state.get("meeting_summary") or {}
    risk_flags = state.get("risk_flags") or []
    lead_score = _coerce_lead_score(state.get("lead_score", 0))

    # 按当前 spec，missing_required_facts 只允许精确等于这个列表时命中，避免被误读成“包含即命中”。
    # 空摘要或解析失败时也先走补充信息分支，避免过早进入跟进或 CRM 写回。
    if not meeting_summary or lead_score is None or risk_flags == ["missing_required_facts"]:
        return "need_more_info"
    if lead_score < 50:
        return "low_priority_nurture"
    if lead_score < 80:
        return "standard_follow_up"
    return "high_priority_follow_up"


def build_sales_copilot_graph(*, llm_client, database_path) -> Any:
    del llm_client, database_path

    builder = StateGraph(SalesCopilotState)

    builder.add_node("ingest_files", _stub_node("ingest_files"))
    builder.add_node("parse_meeting_note", _stub_node("parse_meeting_note"))
    builder.add_node("retrieve_context", _stub_node("retrieve_context"))
    builder.add_node("load_account_memory", _stub_node("load_account_memory"))
    builder.add_node("evaluate_lead", _stub_node("evaluate_lead"))
    builder.add_node("need_more_info", _stub_node("need_more_info"))
    builder.add_node("low_priority_nurture", _stub_node("low_priority_nurture"))
    builder.add_node("standard_follow_up", _stub_node("standard_follow_up"))
    builder.add_node("high_priority_follow_up", _stub_node("high_priority_follow_up"))
    builder.add_node("write_back_crm", _stub_node("write_back_crm"))
    builder.add_node("generate_dashboard_output", _stub_node("generate_dashboard_output"))

    builder.set_entry_point("ingest_files")
    builder.add_edge("ingest_files", "parse_meeting_note")
    builder.add_edge("parse_meeting_note", "retrieve_context")
    builder.add_edge("retrieve_context", "load_account_memory")
    builder.add_edge("load_account_memory", "evaluate_lead")

    builder.add_conditional_edges(
        "evaluate_lead",
        route_after_lead_evaluation,
        {
            "need_more_info": "need_more_info",
            "low_priority_nurture": "low_priority_nurture",
            "standard_follow_up": "standard_follow_up",
            "high_priority_follow_up": "high_priority_follow_up",
        },
    )

    builder.add_edge("need_more_info", "generate_dashboard_output")
    builder.add_edge("low_priority_nurture", "write_back_crm")
    builder.add_edge("standard_follow_up", "write_back_crm")
    builder.add_edge("high_priority_follow_up", "write_back_crm")
    builder.add_edge("write_back_crm", "generate_dashboard_output")
    builder.add_edge("generate_dashboard_output", END)

    return builder.compile()
