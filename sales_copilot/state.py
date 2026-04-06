from typing import Any, TypedDict


class SalesCopilotState(TypedDict, total=False):
    # 这些字段先把工作流骨架固定住，后续任务再逐步往里填真实业务数据。
    account_id: int
    meeting_id: int
    customer_profile_raw: str
    meeting_note_raw: str
    customer_profile_structured: dict[str, Any]
    meeting_summary: dict[str, Any]
    meeting_summary_provided: bool
    retrieved_docs: list[dict[str, Any]]
    account_memory: dict[str, Any]
    open_tasks: list[dict[str, Any]]
    lead_score: int
    lead_priority: str
    opportunity_stage: str
    risk_flags: list[str]
    follow_up_plan: dict[str, Any]
    crm_update_payload: dict[str, Any]
    crm_update_ids: list[int]
    task_payload: list[dict[str, Any]]
    dashboard_output: dict[str, Any]
    workflow_log: list[str]
