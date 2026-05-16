# Sales Copilot stdio MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a real stdio MCP server for the Sales Copilot CRM/Tasks tools, with discovery, schema, invocation, and external verification.

**Architecture:** Keep the existing business tool logic in `sales_copilot/mcp_server.py`, add an explicit schema layer, and wrap it with a real `stdio` MCP server entrypoint using the Python MCP SDK. Preserve the current in-process `mcp` workflow path so demos and evaluations do not regress while adding an external-consumable server.

**Tech Stack:** Python, MCP SDK, LangGraph, SQLite, pytest

---

## File Structure

- `sales_copilot/mcp_server.py`
  Existing business tool layer. May be lightly refactored so stdio server and in-process client share a single source of truth.

- `sales_copilot/mcp_schemas.py`
  New schema metadata module for tool discovery, descriptions, and input schemas.

- `sales_copilot/mcp_stdio_server.py`
  New stdio MCP server implementation using the Python MCP SDK.

- `scripts/run_sales_copilot_mcp_server.py`
  New CLI entrypoint to launch the stdio MCP server.

- `tests/sales_copilot/test_mcp_server.py`
  Existing unit tests for business tool behavior. Keep green.

- `tests/sales_copilot/test_mcp_stdio_server.py`
  New tests for discovery and stdio-facing behavior.

- `README.md`
  Add MCP startup and verification instructions.

### Task 1: Add tool schema metadata

**Files:**
- Create: `D:\minimind\.worktrees\minimind-job-agent\sales_copilot\mcp_schemas.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\sales_copilot\mcp_server.py`
- Test: `D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_mcp_stdio_server.py`

- [ ] **Step 1: Write the failing test**

```python
from sales_copilot.mcp_schemas import TOOL_SCHEMAS


def test_tool_schemas_cover_all_supported_tools():
    assert set(TOOL_SCHEMAS) == {
        "get_account",
        "list_account_tasks",
        "create_task",
        "update_account_stage",
    }
    assert TOOL_SCHEMAS["create_task"]["inputSchema"]["type"] == "object"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_mcp_stdio_server.py::test_tool_schemas_cover_all_supported_tools -v`

Expected: FAIL because `sales_copilot.mcp_schemas` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `sales_copilot/mcp_schemas.py` with a single `TOOL_SCHEMAS` dictionary that defines:

- `name`
- `description`
- `inputSchema`

for all four tools.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_mcp_stdio_server.py::test_tool_schemas_cover_all_supported_tools -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C D:\minimind\.worktrees\minimind-job-agent add sales_copilot/mcp_schemas.py tests/sales_copilot/test_mcp_stdio_server.py
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "feat: add sales copilot mcp tool schemas"
```

### Task 2: Build the stdio MCP server wrapper

**Files:**
- Create: `D:\minimind\.worktrees\minimind-job-agent\sales_copilot\mcp_stdio_server.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\sales_copilot\mcp_server.py`
- Test: `D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_mcp_stdio_server.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from sales_copilot.mcp_stdio_server import build_stdio_server


def test_build_stdio_server_exposes_all_tools(tmp_path: Path):
    server = build_stdio_server(tmp_path / "sales.db")
    tools = server.list_tools()
    names = {tool["name"] for tool in tools}
    assert names == {
        "get_account",
        "list_account_tasks",
        "create_task",
        "update_account_stage",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_mcp_stdio_server.py::test_build_stdio_server_exposes_all_tools -v`

Expected: FAIL because `mcp_stdio_server.py` does not exist.

- [ ] **Step 3: Write minimal implementation**

Implement `build_stdio_server(db_path)` using the MCP SDK. The returned object must:

- register all four tools
- expose tool discovery metadata from `TOOL_SCHEMAS`
- dispatch tool calls to `SalesCopilotMCPServer.call_tool`

Also refactor `mcp_server.py` only if needed to share tool names cleanly.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_mcp_stdio_server.py::test_build_stdio_server_exposes_all_tools -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C D:\minimind\.worktrees\minimind-job-agent add sales_copilot/mcp_stdio_server.py sales_copilot/mcp_server.py tests/sales_copilot/test_mcp_stdio_server.py
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "feat: add stdio mcp server wrapper"
```

### Task 3: Add stdio invocation verification

**Files:**
- Create: `D:\minimind\.worktrees\minimind-job-agent\scripts\run_sales_copilot_mcp_server.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_mcp_stdio_server.py`
- Test: `D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_mcp_stdio_server.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from sales_copilot.mcp_stdio_server import build_stdio_server
from sales_copilot.storage import save_account


def test_stdio_server_call_tool_returns_account_payload(tmp_path: Path):
    db_path = tmp_path / "sales.db"
    account_id = save_account(
        db_path,
        {
            "name": "Acme Robotics",
            "industry": "Manufacturing",
            "size_segment": "Mid-Market",
            "status": "active",
            "opportunity_stage": "discovery",
        },
    )
    server = build_stdio_server(db_path)
    result = server.call_tool("get_account", {"account_id": account_id})
    assert result["account"]["name"] == "Acme Robotics"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_mcp_stdio_server.py::test_stdio_server_call_tool_returns_account_payload -v`

Expected: FAIL because the stdio wrapper does not yet expose a testable tool call path.

- [ ] **Step 3: Write minimal implementation**

Expose a testable helper in `mcp_stdio_server.py` so tests can call tool handlers without standing up an actual subprocess transport. Then add a CLI script:

- `scripts/run_sales_copilot_mcp_server.py --db-path ...`

to launch the stdio server for external consumption.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_mcp_stdio_server.py::test_stdio_server_call_tool_returns_account_payload -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C D:\minimind\.worktrees\minimind-job-agent add sales_copilot/mcp_stdio_server.py scripts/run_sales_copilot_mcp_server.py tests/sales_copilot/test_mcp_stdio_server.py
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "feat: add stdio mcp invocation entrypoint"
```

### Task 4: Protect existing workflow behavior

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\sales_copilot\mcp_client.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\sales_copilot\runner.py`
- Test: `D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_mcp_client.py`

- [ ] **Step 1: Write the failing test**

```python
def test_existing_mcp_client_api_still_wraps_call_tool():
    from sales_copilot.mcp_client import SalesCopilotMCPClient

    class FakeServer:
        def __init__(self):
            self.calls = []
        def call_tool(self, tool_name, arguments=None):
            self.calls.append((tool_name, arguments))
            return {"ok": True}

    client = SalesCopilotMCPClient(FakeServer())
    result = client.get_account(1)
    assert result == {"ok": True}
```

- [ ] **Step 2: Run test to verify it fails only if compatibility breaks**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_mcp_client.py -v`

Expected: PASS before refactor, and must stay PASS after refactor.

- [ ] **Step 3: Refactor minimally if needed**

Only change `mcp_client.py` / `runner.py` if SDK integration requires light compatibility glue. Do not route the current workflow through stdio subprocesses in this task.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_mcp_client.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C D:\minimind\.worktrees\minimind-job-agent add sales_copilot/mcp_client.py sales_copilot/runner.py tests/sales_copilot/test_mcp_client.py
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "refactor: preserve workflow mcp client compatibility"
```

### Task 5: Document and verify end-to-end

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\README.md`
- Test: `D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_mcp_server.py`
- Test: `D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_mcp_client.py`
- Test: `D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_mcp_stdio_server.py`

- [ ] **Step 1: Add README usage section**

Document:

- how to install `mcp`
- how to run `scripts/run_sales_copilot_mcp_server.py`
- what tools are exposed
- what “hard MCP” means in this repo

- [ ] **Step 2: Run focused verification**

Run:

```bash
pytest D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_mcp_server.py -v
pytest D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_mcp_client.py -v
pytest D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_mcp_stdio_server.py -v
```

Expected: all PASS

- [ ] **Step 3: Run broader regression**

Run:

```bash
pytest D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot -q
```

Expected: PASS without MCP regressions

- [ ] **Step 4: Commit**

```bash
git -C D:\minimind\.worktrees\minimind-job-agent add README.md tests/sales_copilot/test_mcp_server.py tests/sales_copilot/test_mcp_client.py tests/sales_copilot/test_mcp_stdio_server.py
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "docs: add stdio mcp server usage"
```

