# Sales Copilot Streaming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a shared structured streaming event pipeline for Sales Copilot that powers CLI real-time output and an app-facing SSE wrapper without breaking the current non-streaming workflow.

**Architecture:** Build a workflow-level generator on top of the existing `DeepSeekClient.stream(...)` provider primitive. Keep `run_sales_copilot(...)` unchanged, add `run_sales_copilot_stream(...)`, and route both CLI and SSE through the same event model so business logic stays in one place.

**Tech Stack:** Python, LangGraph-adjacent workflow code, DeepSeek SSE streaming, PowerShell CLI scripts, pytest

---

### Task 1: Add streaming event helpers

**Files:**
- Create: `D:\minimind\.worktrees\minimind-job-agent\sales_copilot\streaming.py`
- Test: `D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_streaming.py`

- [ ] **Step 1: Write the failing tests**

```python
from sales_copilot.streaming import (
    make_node_started_event,
    make_content_delta_event,
    make_state_patch_event,
)


def test_make_content_delta_event_includes_node_and_text():
    event = make_content_delta_event("parse_meeting_note", "hello")
    assert event == {
        "type": "content_delta",
        "node": "parse_meeting_note",
        "text": "hello",
    }


def test_make_state_patch_event_wraps_patch():
    event = make_state_patch_event("evaluate_lead", {"lead_priority": "high"})
    assert event["type"] == "state_patch"
    assert event["node"] == "evaluate_lead"
    assert event["patch"] == {"lead_priority": "high"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_streaming.py -q`
Expected: FAIL with import error because `sales_copilot.streaming` does not exist yet

- [ ] **Step 3: Write minimal implementation**

```python
def make_node_started_event(node: str, streaming: bool) -> dict:
    return {"type": "node_started", "node": node, "streaming": streaming}


def make_content_delta_event(node: str, text: str) -> dict:
    return {"type": "content_delta", "node": node, "text": text}


def make_state_patch_event(node: str, patch: dict) -> dict:
    return {"type": "state_patch", "node": node, "patch": patch}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_streaming.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add D:/minimind/.worktrees/minimind-job-agent/sales_copilot/streaming.py D:/minimind/.worktrees/minimind-job-agent/tests/sales_copilot/test_streaming.py
git commit -m "feat: add sales copilot streaming event helpers"
```

### Task 2: Add workflow streaming runner

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\sales_copilot\runner.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\sales_copilot\graph.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\sales_copilot\streaming.py`
- Test: `D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_runner.py`

- [ ] **Step 1: Write the failing tests**

```python
from sales_copilot.runner import run_sales_copilot_stream


class FakeStreamingClient:
    def stream(self, messages, tools=None):
        yield {"type": "content_delta", "text": "{\"confirmed_needs\": []}"}
        yield {"type": "message_finished", "finish_reason": "stop"}


def test_run_sales_copilot_stream_emits_workflow_and_node_events(tmp_path):
    events = list(
        run_sales_copilot_stream(
            customer_profile_text="Acme is evaluating sales copilots.",
            meeting_note_text="Customer wants a proposal next week.",
            database_path=tmp_path / "db.sqlite",
            llm_client=FakeStreamingClient(),
        )
    )
    event_types = [event["type"] for event in events]
    assert event_types[0] == "workflow_started"
    assert "node_started" in event_types
    assert event_types[-1] == "workflow_finished"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_runner.py -q -k streaming`
Expected: FAIL because `run_sales_copilot_stream` does not exist

- [ ] **Step 3: Write minimal implementation**

```python
def run_sales_copilot_stream(...):
    yield {"type": "workflow_started", "workflow_name": "sales_copilot", "execution_mode": execution_mode}
    ...
    yield {"type": "node_started", "node": "parse_meeting_note", "streaming": True}
    ...
    yield {"type": "workflow_finished", "result": state}
```

Implementation requirements:
- add a streaming entrypoint alongside `run_sales_copilot(...)`
- keep non-streaming behavior unchanged
- emit `node_started` / `node_finished` for every node
- for LLM nodes, forward provider stream events and accumulate final text for parsing

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_runner.py -q -k streaming`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add D:/minimind/.worktrees/minimind-job-agent/sales_copilot/runner.py D:/minimind/.worktrees/minimind-job-agent/sales_copilot/graph.py D:/minimind/.worktrees/minimind-job-agent/sales_copilot/streaming.py D:/minimind/.worktrees/minimind-job-agent/tests/sales_copilot/test_runner.py
git commit -m "feat: add streaming sales copilot runner"
```

### Task 3: Add CLI streaming renderer

**Files:**
- Create: `D:\minimind\.worktrees\minimind-job-agent\sales_copilot\stream_cli.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\scripts\sales_copilot_web_demo.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\scripts\job_agent_demo.py`
- Test: `D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_stream_cli.py`

- [ ] **Step 1: Write the failing tests**

```python
from sales_copilot.stream_cli import render_stream_event


def test_render_stream_event_formats_node_started():
    line = render_stream_event({"type": "node_started", "node": "evaluate_lead", "streaming": True})
    assert "evaluate_lead" in line
    assert "started" in line.lower()


def test_render_stream_event_formats_tool_call_finished():
    line = render_stream_event(
        {
            "type": "tool_call_finished",
            "node": "evaluate_lead",
            "name": "classify_signal_candidates",
            "arguments": "{\"classifications\": []}",
        }
    )
    assert "classify_signal_candidates" in line
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_stream_cli.py -q`
Expected: FAIL because `sales_copilot.stream_cli` does not exist

- [ ] **Step 3: Write minimal implementation**

```python
def render_stream_event(event: dict) -> str:
    if event["type"] == "node_started":
        return f"[node started] {event['node']}"
    if event["type"] == "tool_call_finished":
        return f"[tool] {event['node']} -> {event['name']}"
    ...
```

Implementation requirements:
- add a dedicated CLI renderer module
- add `--stream` flag to a real workflow script entrypoint
- in `--stream` mode, consume `run_sales_copilot_stream(...)` and print events as they arrive

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_stream_cli.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add D:/minimind/.worktrees/minimind-job-agent/sales_copilot/stream_cli.py D:/minimind/.worktrees/minimind-job-agent/scripts/sales_copilot_web_demo.py D:/minimind/.worktrees/minimind-job-agent/scripts/job_agent_demo.py D:/minimind/.worktrees/minimind-job-agent/tests/sales_copilot/test_stream_cli.py
git commit -m "feat: add cli streaming renderer"
```

### Task 4: Add SSE wrapper

**Files:**
- Create: `D:\minimind\.worktrees\minimind-job-agent\sales_copilot\stream_sse.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\scripts\sales_copilot_web_demo.py`
- Test: `D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_stream_sse.py`

- [ ] **Step 1: Write the failing tests**

```python
from sales_copilot.stream_sse import encode_sse_event


def test_encode_sse_event_serializes_event_type_and_json_payload():
    payload = encode_sse_event({"type": "content_delta", "node": "parse_meeting_note", "text": "hi"})
    assert "event: content_delta" in payload
    assert "\"text\": \"hi\"" in payload
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_stream_sse.py -q`
Expected: FAIL because `sales_copilot.stream_sse` does not exist

- [ ] **Step 3: Write minimal implementation**

```python
def encode_sse_event(event: dict) -> str:
    return f"event: {event['type']}\\ndata: {json.dumps(event, ensure_ascii=False)}\\n\\n"
```

Implementation requirements:
- add a small SSE encoder/wrapper over the shared generator
- keep transport logic separate from workflow logic
- expose a helper suitable for plugging into FastAPI `StreamingResponse`

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_stream_sse.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add D:/minimind/.worktrees/minimind-job-agent/sales_copilot/stream_sse.py D:/minimind/.worktrees/minimind-job-agent/scripts/sales_copilot_web_demo.py D:/minimind/.worktrees/minimind-job-agent/tests/sales_copilot/test_stream_sse.py
git commit -m "feat: add sse wrapper for sales copilot stream"
```

### Task 5: Full verification

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\docs\superpowers\plans\2026-04-13-sales-copilot-streaming.md`

- [ ] **Step 1: Run focused streaming tests**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_streaming.py D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_stream_cli.py D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_stream_sse.py D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_runner.py -q`
Expected: PASS

- [ ] **Step 2: Run broader Sales Copilot test suite**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot -q -k "not mcp_stdio_server"`
Expected: PASS with existing suite still green

- [ ] **Step 3: Run syntax verification**

Run: `@'`
`import py_compile`
`for path in [`
`    r"D:\minimind\.worktrees\minimind-job-agent\sales_copilot\streaming.py",`
`    r"D:\minimind\.worktrees\minimind-job-agent\sales_copilot\stream_cli.py",`
`    r"D:\minimind\.worktrees\minimind-job-agent\sales_copilot\stream_sse.py",`
`    r"D:\minimind\.worktrees\minimind-job-agent\sales_copilot\runner.py",`
`]:`
`    py_compile.compile(path, doraise=True)`
`print("py_compile ok")`
`'@ | python -`
Expected: `py_compile ok`

- [ ] **Step 4: Commit**

```bash
git add D:/minimind/.worktrees/minimind-job-agent
git commit -m "feat: add sales copilot workflow streaming"
```
