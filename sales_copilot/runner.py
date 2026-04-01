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
) -> dict[str, Any]:
    # 这里只做最薄的一层入口，把输入整理成图需要的状态后交给 LangGraph。
    graph = build_sales_copilot_graph(llm_client=llm_client, database_path=database_path)
    state: dict[str, Any] = {
        "customer_profile_raw": customer_profile_text,
        "meeting_note_raw": meeting_note_text,
        "workflow_log": [],
    }
    if account_id is not None:
        state["account_id"] = account_id
    return graph.invoke(state)
