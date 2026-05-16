from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from sales_copilot.mcp_schemas import (
    AccountResponse,
    AccountUpdateResponse,
    TaskCreateResponse,
    TaskListResponse,
    TOOL_SCHEMAS,
)
from sales_copilot.mcp_server import SalesCopilotMCPServer


def build_stdio_server(db_path: Path | str) -> FastMCP:
    db_path = Path(db_path)
    tool_service = SalesCopilotMCPServer(db_path)
    server = FastMCP("Sales Copilot MCP", instructions="CRM and task tools for Sales Copilot.")

    @server.tool(
        name="get_account",
        description=TOOL_SCHEMAS["get_account"]["description"],
        structured_output=True,
    )
    def get_account(account_id: int) -> AccountResponse:
        return AccountResponse.model_validate(tool_service.call_tool("get_account", {"account_id": account_id}))

    @server.tool(
        name="list_account_tasks",
        description=TOOL_SCHEMAS["list_account_tasks"]["description"],
        structured_output=True,
    )
    def list_account_tasks(account_id: int, status: str | None = None) -> TaskListResponse:
        arguments = {"account_id": account_id}
        if status is not None:
            arguments["status"] = status
        return TaskListResponse.model_validate(tool_service.call_tool("list_account_tasks", arguments))

    @server.tool(
        name="create_task",
        description=TOOL_SCHEMAS["create_task"]["description"],
        structured_output=True,
    )
    def create_task(
        account_id: int,
        meeting_id: int,
        title: str,
        description: str,
        priority: str,
        due_at: str,
        status: str = "open",
    ) -> TaskCreateResponse:
        return TaskCreateResponse.model_validate(
            tool_service.call_tool(
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
        )

    @server.tool(
        name="update_account_stage",
        description=TOOL_SCHEMAS["update_account_stage"]["description"],
        structured_output=True,
    )
    def update_account_stage(
        account_id: int,
        status: str,
        opportunity_stage: str,
        last_contact_at: str,
    ) -> AccountUpdateResponse:
        return AccountUpdateResponse.model_validate(
            tool_service.call_tool(
            "update_account_stage",
            {
                "account_id": account_id,
                "status": status,
                "opportunity_stage": opportunity_stage,
                "last_contact_at": last_contact_at,
            },
        )
        )

    return server


async def call_tool_structured(server: FastMCP, name: str, arguments: dict) -> dict:
    result = await server.call_tool(name, arguments)
    if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], dict):
        return result[1]
    if isinstance(result, dict):
        return result
    raise TypeError(f"Unexpected tool result shape for {name}: {type(result)!r}")
