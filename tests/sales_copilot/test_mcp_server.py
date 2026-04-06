from pathlib import Path

from sales_copilot.storage import (
    get_account_by_id,
    list_tasks,
    save_account,
    save_meeting_record,
    save_task_record,
)


def _build_account_record(name: str) -> dict:
    return {
        "name": name,
        "industry": "Technology",
        "size_segment": "Mid-Market",
        "status": "active",
        "opportunity_stage": "discovery",
    }


def test_mcp_server_get_account_returns_account_payload(tmp_path: Path):
    from sales_copilot.mcp_server import SalesCopilotMCPServer

    db_path = tmp_path / "sales.db"
    account_id = save_account(db_path, _build_account_record("Acme Robotics"))
    server = SalesCopilotMCPServer(db_path)

    result = server.call_tool("get_account", {"account_id": account_id})

    assert result["account"]["id"] == account_id
    assert result["account"]["name"] == "Acme Robotics"
    assert result["account"]["opportunity_stage"] == "discovery"


def test_mcp_server_list_account_tasks_filters_by_status(tmp_path: Path):
    from sales_copilot.mcp_server import SalesCopilotMCPServer

    db_path = tmp_path / "sales.db"
    account_id = save_account(db_path, _build_account_record("BluePeak Health"))
    other_account_id = save_account(db_path, _build_account_record("Fabrikam"))
    meeting_id = save_meeting_record(
        db_path,
        {
            "account_id": account_id,
            "meeting_title": "BluePeak Discovery",
            "meeting_note_raw": "Discovery call.",
            "meeting_summary_json": "{}",
            "lead_score": 60,
            "priority": "medium",
        },
    )
    save_task_record(
        db_path,
        {
            "account_id": account_id,
            "meeting_id": meeting_id,
            "title": "Open task",
            "description": "Still open",
            "priority": "medium",
            "due_at": "2026-04-08",
            "status": "open",
        },
    )
    save_task_record(
        db_path,
        {
            "account_id": account_id,
            "meeting_id": meeting_id,
            "title": "Closed task",
            "description": "Already closed",
            "priority": "low",
            "due_at": "2026-04-09",
            "status": "closed",
        },
    )
    other_meeting_id = save_meeting_record(
        db_path,
        {
            "account_id": other_account_id,
            "meeting_title": "Fabrikam Discovery",
            "meeting_note_raw": "Other account call.",
            "meeting_summary_json": "{}",
            "lead_score": 55,
            "priority": "medium",
        },
    )
    save_task_record(
        db_path,
        {
            "account_id": other_account_id,
            "meeting_id": other_meeting_id,
            "title": "Other open task",
            "description": "Belongs to another account",
            "priority": "medium",
            "due_at": "2026-04-10",
            "status": "open",
        },
    )
    server = SalesCopilotMCPServer(db_path)

    result = server.call_tool("list_account_tasks", {"account_id": account_id, "status": "open"})

    assert len(result["tasks"]) == 1
    assert result["tasks"][0]["title"] == "Open task"
    assert result["tasks"][0]["status"] == "open"


def test_mcp_server_create_task_persists_task(tmp_path: Path):
    from sales_copilot.mcp_server import SalesCopilotMCPServer

    db_path = tmp_path / "sales.db"
    account_id = save_account(db_path, _build_account_record("Northwind Traders"))
    meeting_id = save_meeting_record(
        db_path,
        {
            "account_id": account_id,
            "meeting_title": "Northwind Discovery",
            "meeting_note_raw": "Discovery call.",
            "meeting_summary_json": "{}",
            "lead_score": 72,
            "priority": "high",
        },
    )
    server = SalesCopilotMCPServer(db_path)

    result = server.call_tool(
        "create_task",
        {
            "account_id": account_id,
            "meeting_id": meeting_id,
            "title": "Schedule workshop",
            "description": "Book the technical workshop",
            "priority": "high",
            "due_at": "2026-04-10",
            "status": "open",
        },
    )

    tasks = list_tasks(db_path)
    assert result["task_id"] == tasks[0]["id"]
    assert tasks[0]["title"] == "Schedule workshop"
    assert tasks[0]["description"] == "Book the technical workshop"


def test_mcp_server_update_account_stage_updates_account(tmp_path: Path):
    from sales_copilot.mcp_server import SalesCopilotMCPServer

    db_path = tmp_path / "sales.db"
    account_id = save_account(db_path, _build_account_record("Contoso"))
    other_account_id = save_account(db_path, _build_account_record("Tailspin"))
    server = SalesCopilotMCPServer(db_path)

    result = server.call_tool(
        "update_account_stage",
        {
            "account_id": account_id,
            "status": "active",
            "opportunity_stage": "proposal",
            "last_contact_at": "2026-04-06",
        },
    )

    account = get_account_by_id(db_path, account_id)
    other_account = get_account_by_id(db_path, other_account_id)
    assert result["account"]["opportunity_stage"] == "proposal"
    assert account["opportunity_stage"] == "proposal"
    assert account["last_contact_at"] == "2026-04-06"
    assert other_account["opportunity_stage"] == "discovery"


def test_mcp_server_update_account_stage_rejects_missing_account(tmp_path: Path):
    from sales_copilot.mcp_server import SalesCopilotMCPServer

    server = SalesCopilotMCPServer(tmp_path / "sales.db")

    try:
        server.call_tool(
            "update_account_stage",
            {
                "account_id": 999,
                "status": "active",
                "opportunity_stage": "proposal",
                "last_contact_at": "2026-04-06",
            },
        )
    except ValueError as exc:
        assert "does not exist" in str(exc)
    else:
        raise AssertionError("Expected missing account update to raise ValueError")


def test_mcp_server_rejects_missing_required_arguments(tmp_path: Path):
    from sales_copilot.mcp_server import SalesCopilotMCPServer

    server = SalesCopilotMCPServer(tmp_path / "sales.db")

    try:
        server.call_tool("get_account", {})
    except ValueError as exc:
        assert "Invalid arguments" in str(exc)
        assert "account_id" in str(exc)
    else:
        raise AssertionError("Expected missing account_id to raise ValueError")


def test_mcp_server_rejects_unsupported_tool(tmp_path: Path):
    from sales_copilot.mcp_server import SalesCopilotMCPServer

    server = SalesCopilotMCPServer(tmp_path / "sales.db")

    try:
        server.call_tool("delete_everything", {})
    except ValueError as exc:
        assert "Unsupported MCP tool" in str(exc)
    else:
        raise AssertionError("Expected unsupported tool to raise ValueError")
