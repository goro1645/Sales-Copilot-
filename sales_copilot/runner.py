from __future__ import annotations

from pathlib import Path
from typing import Any

from sales_copilot.graph import build_sales_copilot_graph


def run_sales_copilot(
    *,
    customer_profile_text: str,
    meeting_note_text: str,
    database_path: Path | str,
    llm_client,
    account_id: int | None = None,
    meeting_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # 这里仅整理图所需状态；评测已拿到 parse 结果时可直接复用，避免重复请求模型。
    graph = build_sales_copilot_graph(llm_client=llm_client, database_path=database_path)
    state: dict[str, Any] = {
        "customer_profile_raw": customer_profile_text,
        "meeting_note_raw": meeting_note_text,
        "workflow_log": [],
    }
    if account_id is not None:
        state["account_id"] = account_id
    if meeting_summary is not None:
        state["meeting_summary"] = dict(meeting_summary)
    return graph.invoke(state)
