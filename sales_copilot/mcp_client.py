from __future__ import annotations

from typing import Any


class SalesCopilotMCPClient:
    def __init__(self, server) -> None:
        if server is None:
            raise ValueError("MCP client requires a server instance")
        self.server = server

    def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None):
        return self.server.call_tool(tool_name, arguments or {})

    def get_account(self, account_id: int):
        return self.call_tool("get_account", {"account_id": account_id})

    def list_account_tasks(self, account_id: int, status: str | None = None):
        arguments: dict[str, Any] = {"account_id": account_id}
        if status is not None:
            arguments["status"] = status
        return self.call_tool("list_account_tasks", arguments)

    def create_task(
        self,
        *,
        account_id: int,
        meeting_id: int,
        title: str,
        description: str,
        priority: str,
        due_at: str,
        status: str = "open",
    ):
        return self.call_tool(
            "create_task",
            {
                "account_id": account_id,
                "meeting_id": meeting_id,
                "title": title,
                "description": description,
                "priority": priority,
                "due_at": due_at,
                "status": status,
            },
        )

    def update_account_stage(
        self,
        *,
        account_id: int,
        status: str,
        opportunity_stage: str,
        last_contact_at: str,
    ):
        return self.call_tool(
            "update_account_stage",
            {
                "account_id": account_id,
                "status": status,
                "opportunity_stage": opportunity_stage,
                "last_contact_at": last_contact_at,
            },
        )
