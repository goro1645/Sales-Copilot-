import pytest


class FakeMCPServer:
    def __init__(self):
        self.calls = []

    def call_tool(self, tool_name, arguments=None):
        self.calls.append((tool_name, arguments))
        return {"tool_name": tool_name, "arguments": arguments, "metadata": {"echo": True}}


def test_mcp_client_get_account_calls_server():
    from sales_copilot.mcp_client import SalesCopilotMCPClient

    server = FakeMCPServer()
    client = SalesCopilotMCPClient(server)

    result = client.get_account(42)

    assert result == {"tool_name": "get_account", "arguments": {"account_id": 42}, "metadata": {"echo": True}}
    assert server.calls == [("get_account", {"account_id": 42})]


def test_mcp_client_list_account_tasks_calls_server():
    from sales_copilot.mcp_client import SalesCopilotMCPClient

    server = FakeMCPServer()
    client = SalesCopilotMCPClient(server)

    result = client.list_account_tasks(42, status="open")

    assert result == {
        "tool_name": "list_account_tasks",
        "arguments": {"account_id": 42, "status": "open"},
        "metadata": {"echo": True},
    }
    assert server.calls == [("list_account_tasks", {"account_id": 42, "status": "open"})]


def test_mcp_client_create_task_calls_server():
    from sales_copilot.mcp_client import SalesCopilotMCPClient

    server = FakeMCPServer()
    client = SalesCopilotMCPClient(server)

    result = client.create_task(
        account_id=42,
        meeting_id=7,
        title="Schedule workshop",
        description="Book the technical workshop",
        priority="high",
        due_at="2026-04-10",
    )

    assert result == {
        "tool_name": "create_task",
        "arguments": {
            "account_id": 42,
            "meeting_id": 7,
            "title": "Schedule workshop",
            "description": "Book the technical workshop",
            "priority": "high",
            "due_at": "2026-04-10",
        },
        "metadata": {"echo": True},
    }
    assert server.calls == [
        (
            "create_task",
            {
                "account_id": 42,
                "meeting_id": 7,
                "title": "Schedule workshop",
                "description": "Book the technical workshop",
                "priority": "high",
                "due_at": "2026-04-10",
            },
        )
    ]


def test_mcp_client_update_account_stage_calls_server():
    from sales_copilot.mcp_client import SalesCopilotMCPClient

    server = FakeMCPServer()
    client = SalesCopilotMCPClient(server)

    result = client.update_account_stage(
        account_id=42,
        status="active",
        opportunity_stage="proposal",
        last_contact_at="2026-04-06",
    )

    assert result == {
        "tool_name": "update_account_stage",
        "arguments": {
            "account_id": 42,
            "status": "active",
            "opportunity_stage": "proposal",
            "last_contact_at": "2026-04-06",
        },
        "metadata": {"echo": True},
    }
    assert server.calls == [
        (
            "update_account_stage",
            {
                "account_id": 42,
                "status": "active",
                "opportunity_stage": "proposal",
                "last_contact_at": "2026-04-06",
            },
        )
    ]


def test_mcp_client_rejects_none_server():
    from sales_copilot.mcp_client import SalesCopilotMCPClient

    with pytest.raises(ValueError, match="server"):
        SalesCopilotMCPClient(None)
