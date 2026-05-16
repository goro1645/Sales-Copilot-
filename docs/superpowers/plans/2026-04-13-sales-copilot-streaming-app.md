# Sales Copilot Streaming App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Sales Copilot SSE API and make the Streamlit demo consume it to show one continuous live workflow log while preserving the existing final dashboard rendering.

**Architecture:** Build a dedicated FastAPI wrapper around `run_sales_copilot_stream(...)`, encode events with the shared SSE helper, and move Streamlit to a client role that posts workflow input to the API, parses SSE events, and renders a single live log plus the final result.

**Tech Stack:** Python, FastAPI, StreamingResponse/SSE, requests, Streamlit, pytest

---

### Task 1: Add Sales Copilot streaming API

**Files:**
- Create: `D:\minimind\.worktrees\minimind-job-agent\sales_copilot\stream_api.py`
- Create: `D:\minimind\.worktrees\minimind-job-agent\scripts\run_sales_copilot_stream_api.py`
- Test: `D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_stream_api.py`

- [ ] **Step 1: Write the failing tests**

```python
from fastapi.testclient import TestClient

from sales_copilot.stream_api import create_sales_copilot_stream_app


def test_stream_api_returns_sse_frames_from_workflow_events():
    def fake_runner(**kwargs):
        del kwargs
        yield {"type": "workflow_started", "workflow_name": "sales_copilot", "execution_mode": "direct"}
        yield {"type": "workflow_finished", "result": {"lead_priority": "high"}}

    app = create_sales_copilot_stream_app(workflow_runner=fake_runner)
    client = TestClient(app)

    with client.stream(
        "POST",
        "/sales-copilot/stream",
        json={
            "customer_profile_text": "Acme",
            "meeting_note_text": "Need proposal",
            "database_path": "tmp.db",
            "api_key": "test-key",
        },
    ) as response:
        body = "".join(chunk.decode() if isinstance(chunk, bytes) else chunk for chunk in response.iter_lines())

    assert response.status_code == 200
    assert "event: workflow_started" in body
    assert "event: workflow_finished" in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_stream_api.py -q`
Expected: FAIL because `sales_copilot.stream_api` does not exist

- [ ] **Step 3: Write minimal implementation**

Implementation requirements:
- define a request model carrying:
  - `customer_profile_text`
  - `meeting_note_text`
  - `database_path`
  - `execution_mode`
  - `api_key`
  - `api_base_url`
  - `api_model`
- create `create_sales_copilot_stream_app(...)`
- expose `POST /sales-copilot/stream`
- instantiate `DeepSeekClient`
- optionally construct MCP client for `execution_mode="mcp"`
- stream the output of `run_sales_copilot_stream(...)` through `iter_sse_events(...)`

```python
def create_sales_copilot_stream_app(*, workflow_runner=run_sales_copilot_stream) -> FastAPI:
    app = FastAPI()

    @app.post("/sales-copilot/stream")
    def stream_route(request: SalesCopilotStreamRequest):
        ...
        return StreamingResponse(iter_sse_events(...), media_type="text/event-stream")

    return app
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_stream_api.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add D:/minimind/.worktrees/minimind-job-agent/sales_copilot/stream_api.py D:/minimind/.worktrees/minimind-job-agent/scripts/run_sales_copilot_stream_api.py D:/minimind/.worktrees/minimind-job-agent/tests/sales_copilot/test_stream_api.py
git commit -m "feat: add sales copilot streaming api"
```

### Task 2: Add SSE parsing helpers for the app client

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\scripts\sales_copilot_web_utils.py`
- Test: `D:\minimind\.worktrees\minimind-job-agent\tests\scripts\test_sales_copilot_web_utils.py`

- [ ] **Step 1: Write the failing tests**

```python
from scripts.sales_copilot_web_utils import (
    append_stream_log_line,
    build_stream_api_payload,
    parse_sse_event_block,
)


def test_build_stream_api_payload_keeps_runtime_fields():
    payload = build_stream_api_payload(
        customer_profile_text="Acme",
        meeting_note_text="Need proposal",
        database_path="tmp.db",
        execution_mode="direct",
        api_key="key",
        api_base_url="https://api.deepseek.com",
        api_model="deepseek-chat",
    )
    assert payload["execution_mode"] == "direct"
    assert payload["api_model"] == "deepseek-chat"


def test_parse_sse_event_block_returns_event_dict():
    event = parse_sse_event_block("event: workflow_started\\ndata: {\"type\":\"workflow_started\",\"workflow_name\":\"sales_copilot\"}")
    assert event["type"] == "workflow_started"


def test_append_stream_log_line_accumulates_readable_log():
    text = append_stream_log_line("", {"type": "node_started", "node": "parse_meeting_note", "streaming": True})
    assert "parse_meeting_note" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\scripts\test_sales_copilot_web_utils.py -q -k "stream"`
Expected: FAIL because the helper functions do not exist yet

- [ ] **Step 3: Write minimal implementation**

Implementation requirements:
- add a helper to build the API POST payload
- add a helper to parse one SSE event block into a dict
- add a helper that reuses `render_stream_event(...)` to append one readable line into a single log string

```python
def build_stream_api_payload(...): ...
def parse_sse_event_block(block: str) -> dict[str, Any] | None: ...
def append_stream_log_line(log_text: str, event: dict[str, Any]) -> str: ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\scripts\test_sales_copilot_web_utils.py -q -k "stream"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add D:/minimind/.worktrees/minimind-job-agent/scripts/sales_copilot_web_utils.py D:/minimind/.worktrees/minimind-job-agent/tests/scripts/test_sales_copilot_web_utils.py
git commit -m "feat: add app-side sales copilot stream helpers"
```

### Task 3: Update Streamlit demo to consume SSE and render live log

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\scripts\sales_copilot_web_demo.py`
- Test: `D:\minimind\.worktrees\minimind-job-agent\tests\scripts\test_sales_copilot_web_utils.py`

- [ ] **Step 1: Write the failing regression-style test**

```python
from scripts.sales_copilot_web_utils import parse_sse_event_block


def test_stream_helpers_can_extract_final_result_event():
    event = parse_sse_event_block(
        "event: workflow_finished\\n"
        "data: {\"type\":\"workflow_finished\",\"result\":{\"dashboard_output\":{\"account_name\":\"Acme\"}}}"
    )
    assert event["result"]["dashboard_output"]["account_name"] == "Acme"
```

- [ ] **Step 2: Run test to verify it fails if parser is incomplete**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\scripts\test_sales_copilot_web_utils.py -q -k "final_result or stream"`
Expected: FAIL until parser can recover final result payload correctly

- [ ] **Step 3: Write minimal implementation**

Implementation requirements:
- add `stream_api_base_url` to sidebar defaults and controls
- on Run:
  - validate API key and stream API URL
  - POST to `/sales-copilot/stream`
  - read the SSE response incrementally
  - keep one growing text log using `append_stream_log_line(...)`
  - capture final workflow result from `workflow_finished`
  - store final result into `st.session_state["last_result"]`
- keep existing dashboard / CRM / tasks rendering after completion
- preserve non-streaming error handling semantics in the UI

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\scripts\test_sales_copilot_web_utils.py -q -k "stream or final_result"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add D:/minimind/.worktrees/minimind-job-agent/scripts/sales_copilot_web_demo.py D:/minimind/.worktrees/minimind-job-agent/tests/scripts/test_sales_copilot_web_utils.py
git commit -m "feat: stream sales copilot demo through sse api"
```

### Task 4: Full verification

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\docs\superpowers\plans\2026-04-13-sales-copilot-streaming-app.md`

- [ ] **Step 1: Run focused new tests**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_stream_api.py D:\minimind\.worktrees\minimind-job-agent\tests\scripts\test_sales_copilot_web_utils.py -q`
Expected: PASS

- [ ] **Step 2: Run broader streaming-related suites**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_streaming.py D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_stream_cli.py D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_stream_sse.py D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_stream_api.py D:\minimind\.worktrees\minimind-job-agent\tests\scripts\test_sales_copilot_web_utils.py -q`
Expected: PASS

- [ ] **Step 3: Run broader Sales Copilot regression suite**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot -q -k "not mcp_stdio_server"`
Expected: PASS

- [ ] **Step 4: Run syntax verification**

Run: `@'`
`import py_compile`
`for path in [`
`    r"D:\minimind\.worktrees\minimind-job-agent\sales_copilot\stream_api.py",`
`    r"D:\minimind\.worktrees\minimind-job-agent\scripts\run_sales_copilot_stream_api.py",`
`    r"D:\minimind\.worktrees\minimind-job-agent\scripts\sales_copilot_web_demo.py",`
`    r"D:\minimind\.worktrees\minimind-job-agent\scripts\sales_copilot_web_utils.py",`
`]:`
`    py_compile.compile(path, doraise=True)`
`print("py_compile ok")`
`'@ | python -`
Expected: `py_compile ok`

- [ ] **Step 5: Commit**

```bash
git add D:/minimind/.worktrees/minimind-job-agent
git commit -m "feat: add app streaming for sales copilot"
```
