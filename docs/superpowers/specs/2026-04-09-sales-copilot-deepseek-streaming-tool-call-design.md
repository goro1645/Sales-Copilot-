# Sales Copilot DeepSeek Streaming Tool Call Design

## Goal

Add a production-style DeepSeek streaming tool-call path that can consume the official SSE stream, surface incremental text and `tool_calls`, and plug into the existing Sales Copilot codebase without breaking the current non-streaming evaluation and demo flows.

## Scope

This design covers:

- a streaming-capable DeepSeek client
- parsing DeepSeek SSE chunks into normalized events
- a minimal tool-loop runner that can execute tools after streamed `tool_calls`
- one demo/smoke-test entrypoint for real validation
- automated tests for plain text streaming, streamed tool-calls, and error handling

This design does **not** cover:

- replacing all current non-streaming `DeepSeekClient.complete(...)` call sites
- changing CSDS/offline evaluation to stream mode
- adding reasoning-mode specific multi-turn recovery for `deepseek-reasoner`

## Recommended Approach

Use a **dual-path client**:

1. keep the existing `complete(...)` path for stable parse/eval workflows
2. add a new streaming API for official DeepSeek SSE responses
3. build a small tool-loop adapter on top of the streaming API

This is preferred over a stream-first rewrite because the existing parse/evaluation pipeline is already stable and should not be destabilized by transport changes.

## Architecture

### 1. LLM Client Layer

Extend `llm/deepseek_client.py` with a streaming method that:

- sends `stream=true`
- iterates over SSE lines from DeepSeek
- normalizes response chunks into event dictionaries such as:
  - `{"type": "content_delta", "text": "..."}`
  - `{"type": "tool_call_delta", "index": 0, "id": "...", "name": "...", "arguments_delta": "..."}`
  - `{"type": "tool_call_finished", "index": 0, "name": "...", "arguments": "..."}`
  - `{"type": "message_finished", "finish_reason": "..."}`

The existing `complete(...)` API remains unchanged.

### 2. Streaming Tool Loop Layer

Add a small helper module that:

- consumes normalized stream events
- accumulates partial tool-call arguments
- executes local tools only after the streamed tool call is complete
- returns a transcript that can be displayed in demos or reused by future UI integrations

The first tool-loop version only needs to support sequential tool calls.

### 3. Demo / Validation Layer

Add one standalone script that:

- sends a tool-enabled prompt to DeepSeek
- prints streamed text deltas live
- prints streamed tool-call deltas live
- executes the requested local tool
- optionally sends the tool result back for a follow-up completion

This gives us a concrete proof that DeepSeek streaming tool calls work end-to-end in the repo.

## File Plan

### Modify

- `D:\minimind\.worktrees\minimind-job-agent\llm\base.py`
  - add a minimal optional streaming interface contract
- `D:\minimind\.worktrees\minimind-job-agent\llm\deepseek_client.py`
  - add SSE streaming support and chunk normalization
- `D:\minimind\.worktrees\minimind-job-agent\README.md`
  - document the new DeepSeek streaming tool-call path

### Create

- `D:\minimind\.worktrees\minimind-job-agent\llm\streaming.py`
  - event accumulation helpers and tool-call assembly utilities
- `D:\minimind\.worktrees\minimind-job-agent\scripts\deepseek_stream_tool_demo.py`
  - runnable smoke-test/demo entrypoint
- `D:\minimind\.worktrees\minimind-job-agent\tests\llm\test_deepseek_streaming_client.py`
  - client streaming unit tests
- `D:\minimind\.worktrees\minimind-job-agent\tests\llm\test_streaming_tool_loop.py`
  - normalized event/tool-loop tests

## Event Model

The normalized event layer should hide provider-specific chunk shapes from the rest of the app.

Proposed event types:

- `content_delta`
- `tool_call_delta`
- `tool_call_finished`
- `message_finished`
- `error`

This keeps the streaming transport isolated from workflow code and makes future provider swaps easier.

## Error Handling

The streaming path must:

- raise clear errors for malformed SSE frames
- tolerate empty heartbeat lines and `[DONE]`
- surface incomplete tool-call JSON as an `error` event instead of silently swallowing it
- keep non-streaming `complete(...)` behavior unchanged

## Testing Strategy

Tests should cover:

1. plain text SSE stream -> normalized `content_delta`
2. streamed `tool_calls` split across multiple chunks
3. final tool-call assembly into complete JSON arguments
4. `[DONE]` handling and finish reason propagation
5. malformed chunk / invalid JSON handling
6. tool-loop execution after a completed streamed tool call

Tests must mock HTTP responses and must not call the real DeepSeek API.

## Success Criteria

This feature is complete when:

- `DeepSeekClient` can stream normalized text and tool-call events from official SSE
- the repo includes a runnable DeepSeek streaming tool-call demo
- tests cover streamed `tool_calls` and pass locally
- existing non-streaming tests still pass

## Non-Goals

- no UI-first streaming redesign for the Sales Copilot Streamlit workbench yet
- no automatic migration of existing parse/eval nodes to stream mode
- no multi-provider generic streaming abstraction beyond what DeepSeek needs today
