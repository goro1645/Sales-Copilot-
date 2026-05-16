import asyncio
from pathlib import Path

from sales_copilot.storage import save_account, save_meeting_record


def _build_account_record(name: str) -> dict:
    return {
        "name": name,
        "industry": "Technology",
        "size_segment": "Mid-Market",
        "status": "active",
        "opportunity_stage": "discovery",
    }


def test_tool_schemas_cover_all_supported_tools():
    from sales_copilot.mcp_schemas import TOOL_SCHEMAS

    assert set(TOOL_SCHEMAS) == {
        "get_account",
        "list_account_tasks",
        "create_task",
        "update_account_stage",
    }
    assert TOOL_SCHEMAS["create_task"]["inputSchema"]["type"] == "object"


def test_build_stdio_server_exposes_all_tools(tmp_path: Path):
    from sales_copilot.mcp_stdio_server import build_stdio_server

    server = build_stdio_server(tmp_path / "sales.db")
    tools = asyncio.run(server.list_tools())
    names = {tool.name for tool in tools}

    assert names == {
        "get_account",
        "list_account_tasks",
        "create_task",
        "update_account_stage",
    }


def test_stdio_server_call_tool_returns_account_payload(tmp_path: Path):
    from sales_copilot.mcp_stdio_server import build_stdio_server, call_tool_structured

    db_path = tmp_path / "sales.db"
    account_id = save_account(db_path, _build_account_record("Acme Robotics"))
    server = build_stdio_server(db_path)

    result = asyncio.run(call_tool_structured(server, "get_account", {"account_id": account_id}))

    assert isinstance(result, dict)
    assert result["account"]["name"] == "Acme Robotics"


def test_stdio_server_call_tool_creates_task(tmp_path: Path):
    from sales_copilot.mcp_stdio_server import build_stdio_server, call_tool_structured

    db_path = tmp_path / "sales.db"
    account_id = save_account(db_path, _build_account_record("BluePeak Health"))
    meeting_id = save_meeting_record(
        db_path,
        {
            "account_id": account_id,
            "meeting_title": "Qualification",
            "meeting_note_raw": "Need workshop.",
            "meeting_summary_json": "{}",
            "lead_score": 72,
            "priority": "high",
        },
    )
    server = build_stdio_server(db_path)

    result = asyncio.run(
        call_tool_structured(
            server,
            "create_task",
            {
                "account_id": account_id,
                "meeting_id": meeting_id,
                "title": "Schedule workshop",
                "description": "Book technical workshop",
                "priority": "high",
                "due_at": "2026-04-10",
                "status": "open",
            },
        )
    )

    assert isinstance(result, dict)
    assert "task_id" in result


def test_external_client_can_consume_stdio_server(tmp_path: Path):
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    db_path = tmp_path / "sales.db"
    account_id = save_account(db_path, _build_account_record("Contoso"))
    script_path = Path(r"D:\minimind\.worktrees\minimind-job-agent\scripts\run_sales_copilot_mcp_server.py")
    repo_root = script_path.parents[1]

    async def _run() -> tuple[list[str], dict]:
        params = StdioServerParameters(
            command=r"D:\anaconda\envs\minimind_job_agent\python.exe",
            args=[str(script_path), "--db-path", str(db_path)],
            cwd=str(repo_root),
        )
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tool_result = await session.list_tools()
                call_result = await session.call_tool("get_account", {"account_id": account_id})
                return [tool.name for tool in tool_result.tools], call_result.structuredContent

    tool_names, structured_content = asyncio.run(_run())

    assert set(tool_names) == {
        "get_account",
        "list_account_tasks",
        "create_task",
        "update_account_stage",
    }
    assert structured_content["account"]["name"] == "Contoso"
