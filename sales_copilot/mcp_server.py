from __future__ import annotations

from pathlib import Path

from sales_copilot.storage import (
    get_account_by_id,
    list_tasks,
    save_task_record,
    update_account_stage_and_status,
)


class SalesCopilotMCPServer:
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.supported_tools = (
            "get_account",
            "list_account_tasks",
            "create_task",
            "update_account_stage",
        )

    def call_tool(self, tool_name: str, arguments: dict | None = None):
        arguments = arguments or {}

        if tool_name == "get_account":
            account = get_account_by_id(self.db_path, int(arguments["account_id"]))
            if account is None:
                raise ValueError(f"Account {arguments['account_id']} does not exist")
            return {"account": account}

        if tool_name == "list_account_tasks":
            account_id = int(arguments["account_id"])
            status = str(arguments.get("status", "")).strip()
            tasks = [task for task in list_tasks(self.db_path) if task["account_id"] == account_id]
            if status:
                tasks = [task for task in tasks if task["status"] == status]
            return {"tasks": tasks}

        if tool_name == "create_task":
            task_id = save_task_record(
                self.db_path,
                {
                    "account_id": int(arguments["account_id"]),
                    "meeting_id": int(arguments["meeting_id"]),
                    "title": str(arguments["title"]),
                    "description": str(arguments["description"]),
                    "priority": str(arguments["priority"]),
                    "due_at": str(arguments["due_at"]),
                    "status": str(arguments.get("status", "open")),
                },
            )
            return {"task_id": task_id}

        if tool_name == "update_account_stage":
            account_id = int(arguments["account_id"])
            update_account_stage_and_status(
                self.db_path,
                account_id=account_id,
                status=str(arguments["status"]),
                opportunity_stage=str(arguments["opportunity_stage"]),
                last_contact_at=str(arguments.get("last_contact_at", "")),
            )
            account = get_account_by_id(self.db_path, account_id)
            return {"account": account}

        raise ValueError(f"Unsupported MCP tool: {tool_name}")
