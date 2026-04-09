# DeepSeek Streaming Tool Call Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a DeepSeek official SSE streaming tool-call path that can normalize streamed text/tool-call chunks and power a runnable smoke demo without breaking existing non-streaming flows.

**Architecture:** Keep the current `DeepSeekClient.complete(...)` path unchanged for parse/eval stability. Add a dedicated streaming event layer plus a small tool-loop helper, then expose the feature through a standalone demo script instead of forcing the whole Sales Copilot workflow into stream mode immediately.

**Tech Stack:** Python, requests, SSE line parsing, pytest, DeepSeek API

---

## File Map

- `D:\minimind\.worktrees\minimind-job-agent\llm\base.py`
  - add optional streaming interface contract
- `D:\minimind\.worktrees\minimind-job-agent\llm\deepseek_client.py`
  - add `stream(...)` and normalized event emission
- `D:\minimind\.worktrees\minimind-job-agent\llm\streaming.py`
  - event assembly helpers for streamed tool calls
- `D:\minimind\.worktrees\minimind-job-agent\scripts\deepseek_stream_tool_demo.py`
  - smoke-test/demo entrypoint
- `D:\minimind\.worktrees\minimind-job-agent\README.md`
  - usage docs
- `D:\minimind\.worktrees\minimind-job-agent\tests\llm\test_deepseek_streaming_client.py`
  - streaming client tests
- `D:\minimind\.worktrees\minimind-job-agent\tests\llm\test_streaming_tool_loop.py`
  - tool-loop assembly tests

### Task 1: Define streaming event tests

**Files:**
- Create: `D:\minimind\.worktrees\minimind-job-agent\tests\llm\test_deepseek_streaming_client.py`
- Create: `D:\minimind\.worktrees\minimind-job-agent\tests\llm\test_streaming_tool_loop.py`

- [ ] **Step 1: Write failing tests for plain streamed text and streamed tool calls**

```python
def test_deepseek_client_stream_yields_content_and_finish_events():
    ...

def test_deepseek_client_stream_yields_tool_call_deltas_and_finish_event():
    ...

def test_streaming_tool_loop_assembles_complete_tool_call_arguments():
    ...
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run:
`& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest D:\minimind\.worktrees\minimind-job-agent\tests\llm\test_deepseek_streaming_client.py D:\minimind\.worktrees\minimind-job-agent\tests\llm\test_streaming_tool_loop.py -q`

Expected: fail because `DeepSeekClient` has no streaming API yet and `llm.streaming` does not exist.

- [ ] **Step 3: Commit the red tests**

```bash
git add tests/llm/test_deepseek_streaming_client.py tests/llm/test_streaming_tool_loop.py
git commit -m "test: add DeepSeek streaming tool-call coverage"
```

### Task 2: Implement normalized streaming helpers

**Files:**
- Create: `D:\minimind\.worktrees\minimind-job-agent\llm\streaming.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\llm\base.py`

- [ ] **Step 1: Add minimal streaming helper types and assembly logic**

```python
class StreamToolCallAssembler:
    def push_delta(self, *, index: int, tool_id: str | None, name: str | None, arguments_delta: str | None) -> list[dict]:
        ...
```

- [ ] **Step 2: Add an optional streaming contract to the base client**

```python
class BaseLLMClient(ABC):
    ...
    def stream(self, messages: list[dict], tools: list[dict] | None = None):
        raise NotImplementedError
```

- [ ] **Step 3: Run the focused tests**

Run:
`& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest D:\minimind\.worktrees\minimind-job-agent\tests\llm\test_streaming_tool_loop.py -q`

Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add llm/base.py llm/streaming.py tests/llm/test_streaming_tool_loop.py
git commit -m "feat: add streaming tool-call assembly helpers"
```

### Task 3: Add DeepSeek SSE streaming client support

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\llm\deepseek_client.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\tests\llm\test_deepseek_streaming_client.py`

- [ ] **Step 1: Implement `DeepSeekClient.stream(...)` on top of SSE**

```python
def stream(self, messages: list[dict], tools: list[dict] | None = None):
    payload = {"model": self.model, "messages": list(messages), "stream": True}
    ...
    for raw_line in response.iter_lines(decode_unicode=True):
        ...
        yield normalized_event
```

- [ ] **Step 2: Normalize DeepSeek chunks into provider-agnostic events**

```python
{"type": "content_delta", "text": "..."}
{"type": "tool_call_delta", "index": 0, "id": "...", "name": "...", "arguments_delta": "..."}
{"type": "message_finished", "finish_reason": "tool_calls"}
```

- [ ] **Step 3: Run the streaming client tests**

Run:
`& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest D:\minimind\.worktrees\minimind-job-agent\tests\llm\test_deepseek_streaming_client.py -q`

Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add llm/deepseek_client.py tests/llm/test_deepseek_streaming_client.py
git commit -m "feat: add DeepSeek streaming SSE client"
```

### Task 4: Add runnable DeepSeek tool-call demo

**Files:**
- Create: `D:\minimind\.worktrees\minimind-job-agent\scripts\deepseek_stream_tool_demo.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\README.md`

- [ ] **Step 1: Create a small smoke-test script that streams text and tool calls**

```python
TOOLS = [...]

def local_search_sales_playbook(keyword: str) -> str:
    ...

def main():
    ...
    for event in client.stream(..., tools=TOOLS):
        ...
```

- [ ] **Step 2: Document how to run the demo**

```markdown
python scripts/deepseek_stream_tool_demo.py --keyword "private deployment"
```

- [ ] **Step 3: Run syntax verification**

Run:
`& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m py_compile D:\minimind\.worktrees\minimind-job-agent\llm\base.py D:\minimind\.worktrees\minimind-job-agent\llm\deepseek_client.py D:\minimind\.worktrees\minimind-job-agent\llm\streaming.py D:\minimind\.worktrees\minimind-job-agent\scripts\deepseek_stream_tool_demo.py`

Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add scripts/deepseek_stream_tool_demo.py README.md
git commit -m "feat: add DeepSeek streaming tool-call demo"
```

### Task 5: Run final related verification

**Files:**
- Verify only

- [ ] **Step 1: Run the new LLM streaming tests**

Run:
`& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest D:\minimind\.worktrees\minimind-job-agent\tests\llm\test_deepseek_client.py D:\minimind\.worktrees\minimind-job-agent\tests\llm\test_deepseek_streaming_client.py D:\minimind\.worktrees\minimind-job-agent\tests\llm\test_streaming_tool_loop.py -q`

Expected: all pass.

- [ ] **Step 2: Run the existing scripts suite to catch integration regressions**

Run:
`& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest D:\minimind\.worktrees\minimind-job-agent\tests\scripts -q`

Expected: all pass.

- [ ] **Step 3: Commit final cleanups if needed**

```bash
git add -A
git commit -m "test: verify DeepSeek streaming tool-call integration"
```
