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
            account_id = self._require_int(arguments, "account_id", tool_name)
            account = get_account_by_id(self.db_path, account_id)
            if account is None:
                raise ValueError(f"Account {account_id} does not exist")
            return {"account": account}

        if tool_name == "list_account_tasks":
            account_id = self._require_int(arguments, "account_id", tool_name)
            status = str(arguments.get("status", "")).strip()
            tasks = [task for task in list_tasks(self.db_path) if task["account_id"] == account_id]
            if status:
                tasks = [task for task in tasks if task["status"] == status]
            return {"tasks": tasks}

        if tool_name == "create_task":
            task_id = save_task_record(
                self.db_path,
                {
                    "account_id": self._require_int(arguments, "account_id", tool_name),
                    "meeting_id": self._require_int(arguments, "meeting_id", tool_name),
                    "title": self._require_text(arguments, "title", tool_name),
                    "description": self._require_text(arguments, "description", tool_name),
                    "priority": self._require_text(arguments, "priority", tool_name),
                    "due_at": self._require_text(arguments, "due_at", tool_name),
                    "status": str(arguments.get("status", "open")),
                },
            )
            return {"task_id": task_id}

        if tool_name == "update_account_stage":
            account_id = self._require_int(arguments, "account_id", tool_name)
            update_account_stage_and_status(
                self.db_path,
                account_id=account_id,
                status=self._require_text(arguments, "status", tool_name),
                opportunity_stage=self._require_text(arguments, "opportunity_stage", tool_name),
                last_contact_at=str(arguments.get("last_contact_at", "")),
            )
            account = get_account_by_id(self.db_path, account_id)
            if account is None:
                raise ValueError(f"Account {account_id} does not exist")
            return {"account": account}

        raise ValueError(f"Unsupported MCP tool: {tool_name}")

    @staticmethod
    def _require_int(arguments: dict, field_name: str, tool_name: str) -> int:
        if field_name not in arguments:
            raise ValueError(f"Invalid arguments for {tool_name}: missing {field_name}")
        try:
            return int(arguments[field_name])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid arguments for {tool_name}: {field_name} must be an integer") from exc

    @staticmethod
    def _require_text(arguments: dict, field_name: str, tool_name: str) -> str:
        if field_name not in arguments:
            raise ValueError(f"Invalid arguments for {tool_name}: missing {field_name}")
        text = str(arguments[field_name]).strip()
        if not text:
            raise ValueError(f"Invalid arguments for {tool_name}: {field_name} must be non-empty")
        return text
