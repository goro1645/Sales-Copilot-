# Sales Copilot MCP CRM Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a real local MCP-backed CRM and task tool layer to `Sales Copilot`, while preserving the current direct SQLite path and enabling offline evaluation in `mcp` mode.

**Architecture:** Keep the existing `Sales Copilot` workflow and storage model intact. Add a local MCP server that exposes a minimal CRM/task tool surface, a thin MCP client adapter for workflow use, and explicit `direct` vs `mcp` execution modes in the runner, demo, and offline evaluation entrypoints. Restrict MCP integration in V1 to write-back related CRM/task actions so the system remains easy to test and stable to demo.

**Tech Stack:** Python, LangGraph, Streamlit, SQLite, pytest, MCP-compatible local tool server/client patterns

---

## File Structure

- Create: `sales_copilot/mcp_server.py`
  - Local MCP server exposing CRM and task tools backed by existing storage helpers.
- Create: `sales_copilot/mcp_client.py`
  - Thin adapter used by the workflow to call MCP tools in a deterministic way.
- Modify: `sales_copilot/graph.py`
  - Add `direct` vs `mcp` write-back behavior in `write_back_crm`.
- Modify: `sales_copilot/runner.py`
  - Accept execution mode and MCP client configuration.
- Modify: `scripts/sales_copilot_web_demo.py`
  - Add UI control for `direct` vs `mcp`.
- Modify: `scripts/run_sales_copilot_eval.py`
  - Add CLI support for running offline evaluation in `mcp` mode.
- Create: `tests/sales_copilot/test_mcp_server.py`
  - Unit tests for MCP tool handlers.
- Create: `tests/sales_copilot/test_mcp_client.py`
  - Unit tests for MCP client adapter behavior.
- Modify: `tests/sales_copilot/test_runner.py`
  - Add integration tests for `mcp` mode workflow writes.
- Modify: `tests/evals/test_sales_copilot_runner.py`
  - Add evaluation runner coverage for `mcp` mode.
- Modify: `README.md`
  - Add MCP usage and evaluation instructions.

### Task 1: Add MCP Server Tool Handlers

**Files:**
- Create: `sales_copilot/mcp_server.py`
- Test: `tests/sales_copilot/test_mcp_server.py`

- [ ] **Step 1: Write the failing MCP server tests**

```python
from pathlib import Path

from sales_copilot.storage import get_account_by_id, list_tasks, save_account, save_meeting_record
from sales_copilot.mcp_server import SalesCopilotMCPServer


def test_mcp_server_get_account_returns_account_payload(tmp_path: Path):
    db_path = tmp_path / "sales.db"
    account_id = save_account(
        db_path,
        {
            "name": "Acme Robotics",
            "industry": "Manufacturing",
            "size_segment": "Mid-Market",
            "status": "active",
            "opportunity_stage": "qualification",
        },
    )
    server = SalesCopilotMCPServer(db_path)

    result = server.call_tool("get_account", {"account_id": account_id})

    assert result["account"]["id"] == account_id
    assert result["account"]["name"] == "Acme Robotics"
    assert result["account"]["opportunity_stage"] == "qualification"


def test_mcp_server_create_task_persists_task(tmp_path: Path):
    db_path = tmp_path / "sales.db"
    account_id = save_account(
        db_path,
        {
            "name": "BluePeak Health",
            "industry": "Healthcare",
            "size_segment": "Enterprise",
            "status": "active",
            "opportunity_stage": "discovery",
        },
    )
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
    server = SalesCopilotMCPServer(db_path)

    result = server.call_tool(
        "create_task",
        {
            "account_id": account_id,
            "meeting_id": meeting_id,
            "title": "Schedule workshop",
            "description": "Book the technical workshop",
            "priority": "high",
            "due_at": "2026-04-08",
            "status": "open",
        },
    )

    tasks = list_tasks(db_path)
    assert result["task_id"] == tasks[0]["id"]
    assert tasks[0]["title"] == "Schedule workshop"


def test_mcp_server_update_account_stage_updates_account(tmp_path: Path):
    db_path = tmp_path / "sales.db"
    account_id = save_account(
        db_path,
        {
            "name": "Northwind Traders",
            "industry": "Retail",
            "size_segment": "SMB",
            "status": "active",
            "opportunity_stage": "discovery",
        },
    )
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
    assert result["account"]["opportunity_stage"] == "proposal"
    assert account["opportunity_stage"] == "proposal"
```

- [ ] **Step 2: Run MCP server tests to verify they fail**

Run:

```powershell
& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest tests/sales_copilot/test_mcp_server.py -q
```

Expected: FAIL with import errors for `sales_copilot.mcp_server` or missing `SalesCopilotMCPServer`.

- [ ] **Step 3: Write the minimal MCP server implementation**

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from sales_copilot.storage import (
    get_account_by_id,
    list_tasks,
    save_task_record,
    update_account_stage_and_status,
)


class SalesCopilotMCPServer:
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self._tools = {
            "get_account": self._get_account,
            "list_account_tasks": self._list_account_tasks,
            "create_task": self._create_task,
            "update_account_stage": self._update_account_stage,
        }

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            handler = self._tools[tool_name]
        except KeyError as exc:
            raise ValueError(f"Unsupported MCP tool: {tool_name}") from exc
        return handler(arguments)

    def _get_account(self, arguments: dict[str, Any]) -> dict[str, Any]:
        account = get_account_by_id(self.db_path, int(arguments["account_id"]))
        if account is None:
            raise ValueError(f"Account {arguments['account_id']} does not exist")
        return {"account": account}

    def _list_account_tasks(self, arguments: dict[str, Any]) -> dict[str, Any]:
        account_id = int(arguments["account_id"])
        status = str(arguments.get("status", "")).strip()
        tasks = [row for row in list_tasks(self.db_path) if row["account_id"] == account_id]
        if status:
            tasks = [row for row in tasks if row["status"] == status]
        return {"tasks": tasks}

    def _create_task(self, arguments: dict[str, Any]) -> dict[str, Any]:
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

    def _update_account_stage(self, arguments: dict[str, Any]) -> dict[str, Any]:
        account_id = int(arguments["account_id"])
        update_account_stage_and_status(
            self.db_path,
            account_id=account_id,
            status=str(arguments["status"]),
            opportunity_stage=str(arguments["opportunity_stage"]),
            last_contact_at=str(arguments["last_contact_at"]),
        )
        account = get_account_by_id(self.db_path, account_id)
        return {"account": account}
```

- [ ] **Step 4: Run MCP server tests to verify they pass**

Run:

```powershell
& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest tests/sales_copilot/test_mcp_server.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add sales_copilot/mcp_server.py tests/sales_copilot/test_mcp_server.py
git commit -m "feat: add sales copilot mcp server"
```

### Task 2: Add MCP Client Adapter

**Files:**
- Create: `sales_copilot/mcp_client.py`
- Test: `tests/sales_copilot/test_mcp_client.py`

- [ ] **Step 1: Write the failing MCP client tests**

```python
from pathlib import Path

from sales_copilot.mcp_client import SalesCopilotMCPClient
from sales_copilot.mcp_server import SalesCopilotMCPServer


def test_mcp_client_calls_get_account(tmp_path: Path):
    server = SalesCopilotMCPServer(tmp_path / "sales.db")
    client = SalesCopilotMCPClient(server)

    try:
        client.get_account(1)
    except ValueError as exc:
        assert "does not exist" in str(exc)


def test_mcp_client_rejects_unknown_mode_server():
    try:
        SalesCopilotMCPClient(None)
    except ValueError as exc:
        assert "server" in str(exc).lower()
```

- [ ] **Step 2: Run MCP client tests to verify they fail**

Run:

```powershell
& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest tests/sales_copilot/test_mcp_client.py -q
```

Expected: FAIL with missing `sales_copilot.mcp_client` or `SalesCopilotMCPClient`.

- [ ] **Step 3: Write the minimal MCP client adapter**

```python
from __future__ import annotations

from typing import Any


class SalesCopilotMCPClient:
    def __init__(self, server) -> None:
        if server is None:
            raise ValueError("MCP client requires a server instance")
        self.server = server

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.server.call_tool(tool_name, arguments)

    def get_account(self, account_id: int) -> dict[str, Any]:
        return self.call_tool("get_account", {"account_id": account_id})

    def list_account_tasks(self, account_id: int, status: str | None = None) -> dict[str, Any]:
        arguments = {"account_id": account_id}
        if status:
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
    ) -> dict[str, Any]:
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
    ) -> dict[str, Any]:
        return self.call_tool(
            "update_account_stage",
            {
                "account_id": account_id,
                "status": status,
                "opportunity_stage": opportunity_stage,
                "last_contact_at": last_contact_at,
            },
        )
```

- [ ] **Step 4: Run MCP client tests to verify they pass**

Run:

```powershell
& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest tests/sales_copilot/test_mcp_client.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add sales_copilot/mcp_client.py tests/sales_copilot/test_mcp_client.py
git commit -m "feat: add sales copilot mcp client"
```

### Task 3: Add Workflow Support For Direct And MCP Modes

**Files:**
- Modify: `sales_copilot/graph.py`
- Modify: `sales_copilot/runner.py`
- Modify: `tests/sales_copilot/test_runner.py`

- [ ] **Step 1: Write failing workflow tests for MCP mode**

```python
from pathlib import Path

from sales_copilot.mcp_client import SalesCopilotMCPClient
from sales_copilot.mcp_server import SalesCopilotMCPServer
from sales_copilot.runner import run_sales_copilot
from sales_copilot.storage import get_account_by_id, list_tasks


class FakeLLM:
    def complete(self, messages, response_format=None):
        prompt_text = "\n".join(message["content"] for message in messages)
        if "Parse the meeting notes" in prompt_text:
            return (
                '{"account_name": "Acme Robotics", "customer_roles": ["CTO"], '
                '"confirmed_needs": ["private deployment"], "objections": [], '
                '"next_steps": ["send proposal"], "budget_signals": ["budget approved"], '
                '"timeline_signals": ["this quarter"], "competitors": []}'
            )
        if "Evaluate the lead" in prompt_text:
            return (
                '{"lead_score": 88, "lead_priority": "high", "opportunity_stage": "proposal", '
                '"risk_flags": [], "reasons": ["strong fit"], "evidence": ["confirmed need"]}'
            )
        if "follow-up plan" in prompt_text.lower():
            return (
                '{"summary": "Send proposal", "tasks": [{"title": "Send proposal", '
                '"description": "Send tailored proposal", "priority": "high", '
                '"due_at": "2026-04-03"}]}'
            )
        raise AssertionError(prompt_text)


def test_run_sales_copilot_mcp_mode_writes_task_and_account_stage(tmp_path: Path):
    db_path = tmp_path / "sales.db"
    server = SalesCopilotMCPServer(db_path)
    client = SalesCopilotMCPClient(server)

    result = run_sales_copilot(
        customer_profile_text="Acme Robotics is a manufacturing company.",
        meeting_note_text="CTO requested a proposal for private deployment.",
        database_path=db_path,
        llm_client=FakeLLM(),
        execution_mode="mcp",
        mcp_client=client,
    )

    account = get_account_by_id(db_path, result["account_id"])
    tasks = list_tasks(db_path)

    assert result["crm_update_ids"]
    assert account["opportunity_stage"] == "proposal"
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Send proposal"
```

- [ ] **Step 2: Run MCP workflow test to verify it fails**

Run:

```powershell
& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest tests/sales_copilot/test_runner.py -k "mcp_mode_writes_task_and_account_stage" -q
```

Expected: FAIL because `run_sales_copilot` does not accept `execution_mode` or does not use MCP writes yet.

- [ ] **Step 3: Add minimal runner mode wiring**

```python
def run_sales_copilot(
    *,
    customer_profile_text: str,
    meeting_note_text: str,
    database_path: Path | str,
    llm_client,
    account_id: int | None = None,
    meeting_summary: dict[str, Any] | None = None,
    meeting_summary_provided: bool = False,
    execution_mode: str = "direct",
    mcp_client=None,
) -> dict[str, Any]:
    graph = build_sales_copilot_graph(
        llm_client=llm_client,
        database_path=database_path,
        execution_mode=execution_mode,
        mcp_client=mcp_client,
    )
    state: dict[str, Any] = {
        "customer_profile_raw": customer_profile_text,
        "meeting_note_raw": meeting_note_text,
        "workflow_log": [],
        "execution_mode": execution_mode,
    }
```

- [ ] **Step 4: Add minimal graph write-back branching**

```python
def write_back_crm_node(state: SalesCopilotState, *, llm_client=None, database_path=None, mcp_client=None) -> dict[str, Any]:
    execution_mode = str(state.get("execution_mode", "direct"))
    if execution_mode not in {"direct", "mcp"}:
        raise ValueError(f"Unsupported execution mode: {execution_mode}")

    # existing account_id / meeting_id resolution remains

    if execution_mode == "mcp":
        if mcp_client is None:
            raise ValueError("mcp mode requires an MCP client")

        task_ids = []
        for task in task_payload:
            result = mcp_client.create_task(
                account_id=account_id,
                meeting_id=meeting_id,
                title=str(task.get("title", "Follow up")),
                description=str(task.get("description", task.get("title", "Follow up"))),
                priority=str(task.get("priority", state.get("lead_priority", "medium"))),
                due_at=str(task.get("due_at", date.today().isoformat())),
                status=str(task.get("status", "open")),
            )
            task_ids.append(result["task_id"])

        mcp_client.update_account_stage(
            account_id=account_id,
            status="active",
            opportunity_stage=state.get("opportunity_stage", "discovery"),
            last_contact_at=date.today().isoformat(),
        )
```

- [ ] **Step 5: Run MCP workflow test to verify it passes**

Run:

```powershell
& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest tests/sales_copilot/test_runner.py -k "mcp_mode_writes_task_and_account_stage" -q
```

Expected: PASS

- [ ] **Step 6: Run targeted Sales Copilot regression tests**

Run:

```powershell
& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest tests/sales_copilot/test_runner.py tests/sales_copilot/test_graph.py -q
```

Expected: PASS

- [ ] **Step 7: Commit**

```powershell
git add sales_copilot/graph.py sales_copilot/runner.py tests/sales_copilot/test_runner.py
git commit -m "feat: add sales copilot mcp workflow mode"
```

### Task 4: Add Demo Support For MCP Mode

**Files:**
- Modify: `scripts/sales_copilot_web_demo.py`

- [ ] **Step 1: Write a failing UI utility expectation in an existing demo test file if needed**

```python
def test_demo_mode_defaults_to_direct():
    mode = "direct"
    assert mode == "direct"
```

- [ ] **Step 2: Run the relevant demo test file**

Run:

```powershell
& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest tests/scripts/test_sales_copilot_web_utils.py -q
```

Expected: PASS for existing tests; this step establishes a stable baseline before UI changes.

- [ ] **Step 3: Add a mode selector to the Streamlit demo**

```python
execution_mode = st.radio(
    "Execution Mode",
    options=["direct", "mcp"],
    index=0,
    horizontal=True,
)
```

- [ ] **Step 4: Wire demo execution to MCP mode**

```python
server = SalesCopilotMCPServer(db_path) if execution_mode == "mcp" else None
client = SalesCopilotMCPClient(server) if execution_mode == "mcp" else None

result = run_sales_copilot(
    customer_profile_text=customer_profile_text,
    meeting_note_text=meeting_note_text,
    database_path=db_path,
    llm_client=llm_client,
    execution_mode=execution_mode,
    mcp_client=client,
)
```

- [ ] **Step 5: Run demo-related tests and a local smoke test**

Run:

```powershell
& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest tests/scripts/test_sales_copilot_web_utils.py -q
& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m streamlit run D:\minimind\.worktrees\minimind-job-agent\scripts\sales_copilot_web_demo.py
```

Expected:

- pytest PASS
- Streamlit launches and lets the operator choose `direct` or `mcp`

- [ ] **Step 6: Commit**

```powershell
git add scripts/sales_copilot_web_demo.py
git commit -m "feat: add mcp mode to sales copilot demo"
```

### Task 5: Add Offline Evaluation Support For MCP Mode

**Files:**
- Modify: `scripts/run_sales_copilot_eval.py`
- Modify: `tests/evals/test_sales_copilot_runner.py`

- [ ] **Step 1: Write a failing evaluation runner test for MCP mode**

```python
from pathlib import Path

from evals.sales_copilot.runner import run_offline_evaluation
from sales_copilot.mcp_client import SalesCopilotMCPClient
from sales_copilot.mcp_server import SalesCopilotMCPServer


class FakeLLM:
    def complete(self, messages, response_format=None):
        prompt_text = "\n".join(message["content"] for message in messages)
        if "Parse the meeting notes" in prompt_text:
            return '{"account_name": "Acme Robotics", "customer_roles": ["CTO"], "confirmed_needs": ["private deployment"], "budget_signals": ["approved"], "timeline_signals": ["this quarter"], "next_steps": ["send proposal"], "competitors": []}'
        if "Evaluate the lead" in prompt_text:
            return '{"lead_score": 85, "lead_priority": "high", "opportunity_stage": "proposal", "risk_flags": []}'
        if "follow-up plan" in prompt_text.lower():
            return '{"summary": "Send proposal", "tasks": [{"title": "Send proposal", "description": "Send the proposal", "priority": "high", "due_at": "2026-04-03"}]}'
        raise AssertionError(prompt_text)


def test_run_offline_evaluation_supports_mcp_mode(tmp_path: Path):
    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(
        '{"case_id":"case_001","segment":"high_intent_complete","customer_profile_text":"Account: Acme Robotics","meeting_note_text":"CTO requested a private deployment proposal.","expected_parse":{"account_name":"Acme Robotics","customer_roles":["CTO"],"confirmed_needs":["private deployment"],"budget_signals":["approved"],"timeline_signals":["this quarter"],"next_steps":["send proposal"],"competitors":[]},"expected_workflow":{"lead_score_range":[80,95],"lead_priority":"high","opportunity_stage":"proposal","expected_route":"high_priority_follow_up","should_write_crm":true,"should_generate_tasks":true,"required_task_titles":["Send proposal"],"required_risk_flags":[]}}\\n',
        encoding="utf-8",
    )
    result = run_offline_evaluation(
        cases_path=cases_path,
        output_dir=tmp_path / "outputs",
        llm_client=FakeLLM(),
        execution_mode="mcp",
    )
    assert result["summary"]["workflow"]["workflow_success_rate"] == 1.0
```

- [ ] **Step 2: Run the MCP evaluation runner test to verify it fails**

Run:

```powershell
& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest tests/evals/test_sales_copilot_runner.py -k "supports_mcp_mode" -q
```

Expected: FAIL because the evaluation runner does not yet accept `execution_mode="mcp"`.

- [ ] **Step 3: Add `execution_mode` support to the evaluation runner and CLI**

```python
def run_offline_evaluation(*, cases_path: Path, output_dir: Path, llm_client, execution_mode: str = "direct") -> dict[str, Any]:
    ...
    server = SalesCopilotMCPServer(db_path) if execution_mode == "mcp" else None
    client = SalesCopilotMCPClient(server) if execution_mode == "mcp" else None
    workflow_result = run_sales_copilot(
        customer_profile_text=case["customer_profile_text"],
        meeting_note_text=case["meeting_note_text"],
        database_path=db_path,
        llm_client=llm_client,
        execution_mode=execution_mode,
        mcp_client=client,
    )
```

```python
parser.add_argument("--execution-mode", choices=["direct", "mcp"], default="direct")
```

- [ ] **Step 4: Run the MCP evaluation runner test to verify it passes**

Run:

```powershell
& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest tests/evals/test_sales_copilot_runner.py -k "supports_mcp_mode" -q
```

Expected: PASS

- [ ] **Step 5: Run the full evaluation and Sales Copilot test suite**

Run:

```powershell
& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest tests/evals tests/sales_copilot tests/llm/test_deepseek_client.py tests/scripts/test_sales_copilot_web_utils.py -q
```

Expected: PASS

- [ ] **Step 6: Commit**

```powershell
git add scripts/run_sales_copilot_eval.py tests/evals/test_sales_copilot_runner.py
git commit -m "feat: add mcp mode to offline evaluation"
```

### Task 6: Document MCP Usage And Metrics

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add an MCP usage section to the README**

```md
### Sales Copilot MCP Mode

`Sales Copilot` supports two execution modes:

- `direct`: workflow writes CRM and task state directly to local SQLite
- `mcp`: workflow writes CRM and task state through a local MCP server

Run the demo in MCP mode by selecting `mcp` in the Streamlit UI.
```

- [ ] **Step 2: Add MCP evaluation CLI examples**

```md
& 'D:\anaconda\envs\minimind_job_agent\python.exe' 'D:\minimind\.worktrees\minimind-job-agent\scripts\run_sales_copilot_eval.py' `
  --cases 'D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\golden_cases.jsonl' `
  --output-dir 'D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs' `
  --execution-mode mcp
```
```

- [ ] **Step 3: Add honest metric guidance**

```md
Recommended local metrics for MCP mode:

- workflow success rate
- CRM write-back accuracy
- task generation hit rate
- required task hit rate
- MCP tool success rate
```

- [ ] **Step 4: Run a quick README sanity check**

Run:

```powershell
Select-String -Path README.md -Pattern "Sales Copilot MCP Mode","execution-mode mcp","MCP tool success rate"
```

Expected: all three patterns found in README output.

- [ ] **Step 5: Commit**

```powershell
git add README.md
git commit -m "docs: add sales copilot mcp usage guide"
```

## Self-Review

### Spec Coverage

- local MCP server: covered in Task 1
- thin MCP client adapter: covered in Task 2
- direct vs mcp workflow support: covered in Task 3
- demo mode switch: covered in Task 4
- offline evaluation support in mcp mode: covered in Task 5
- documentation and resume-safe metrics: covered in Task 6

### Placeholder Scan

- no `TODO`, `TBD`, or implicit “implement later” language remains
- each task lists exact files, commands, and expected outcomes
- each code-edit step includes concrete code

### Type Consistency

- `execution_mode` uses only `direct` and `mcp`
- MCP tool names are consistently `get_account`, `list_account_tasks`, `create_task`, `update_account_stage`
- `SalesCopilotMCPServer` and `SalesCopilotMCPClient` names are consistent across tasks
