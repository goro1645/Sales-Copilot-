"""Shared workflow state for a single Sales Copilot run.

`SalesCopilotState` is the object passed between LangGraph nodes. Read this file
as the compact glossary of what the system knows at each stage.
"""

from typing import Any, TypedDict


class SalesCopilotState(TypedDict, total=False):
    # 这些字段先把工作流骨架固定住，后续任务再逐步往里填真实业务数据。
    account_id: int
    meeting_id: int
    execution_mode: str
    customer_profile_raw: str
    meeting_note_raw: str
    customer_profile_structured: dict[str, Any]
    meeting_summary: dict[str, Any]
    # parse 结果，最重要的字段包括 confirmed_needs / next_steps / timeline_signals。
    meeting_summary_provided: bool
    retrieved_docs: list[dict[str, Any]]
    # RAG 找回来的外部知识或账户历史片段。
    account_memory: dict[str, Any]
    # 按 account_id 直接读取的长期账户状态，不是向量检索结果。
    open_tasks: list[dict[str, Any]]
    lead_score: int
    lead_priority: str
    opportunity_stage: str
    risk_flags: list[str]
    task_candidates: list[dict[str, Any]]
    # 任务候选中间层，用来减少会议事实在最终任务生成中的丢失。
    follow_up_plan: dict[str, Any]
    crm_update_payload: dict[str, Any]
    crm_update_ids: list[int]
    crm_writeback_performed: bool
    task_payload: list[dict[str, Any]]
    dashboard_output: dict[str, Any]
    workflow_log: list[str]
