# Sales Copilot Streaming App Design

## Goal

Expose the new Sales Copilot workflow streaming pipeline through an application-facing SSE API, then make the existing Streamlit demo consume that API and render a single continuous live log while the workflow runs.

This should build on top of the already-added workflow event generator and should not fork workflow execution logic.

## Why this exists

The current codebase now has:

- provider-level streaming in `llm.deepseek_client.DeepSeekClient.stream(...)`
- workflow-level structured streaming in `sales_copilot.runner.run_sales_copilot_stream(...)`
- CLI/SSE formatting helpers in `sales_copilot.stream_cli` and `sales_copilot.stream_sse`

What is still missing is an application integration path. Right now:

- CLI can consume the stream
- internal Python code can consume the stream
- the existing Streamlit app still runs through the non-streaming code path
- there is no dedicated Sales Copilot SSE endpoint for app or frontend consumption

This design closes that gap.

## Scope

Version 1 covers:

- a dedicated Sales Copilot HTTP streaming endpoint
- SSE output based on the shared workflow event generator
- Streamlit integration that consumes the SSE stream
- a single continuous live log panel in the Streamlit app
- final dashboard / CRM / task rendering after `workflow_finished`

Version 1 does **not** include:

- websocket transport
- multi-user session persistence
- judge/eval streaming in the app
- a new frontend separate from Streamlit

## User experience

### API layer

The app should be able to call a dedicated Sales Copilot API endpoint and receive:

- `text/event-stream`
- structured event names matching the workflow event `type`
- JSON payloads for each event

Expected route shape:

- `POST /sales-copilot/stream`

### Streamlit layer

When the user clicks the run button in the Streamlit demo:

1. the app sends the current form data to the streaming API
2. the app starts reading SSE frames immediately
3. the page shows a single continuously growing log area
4. when the stream finishes, the app renders the final dashboard / CRM / task sections using the final workflow result from `workflow_finished`

The first version should favor clarity over fancy UI. A single continuous log is enough.

## Architecture

### Shared execution core

The workflow execution core remains:

- `sales_copilot.runner.run_sales_copilot_stream(...)`

This is the only business execution source for streaming mode.

### API wrapper

Add a lightweight API wrapper that:

- validates request input
- instantiates `DeepSeekClient`
- calls `run_sales_copilot_stream(...)`
- converts emitted events to SSE frames using `sales_copilot.stream_sse`

This wrapper should not re-implement workflow logic.

### Streamlit consumer

The Streamlit app should:

- keep using the current form inputs
- add an API base URL for the streaming service
- POST to the SSE endpoint
- parse incoming SSE frames
- reuse `sales_copilot.stream_cli.render_stream_event(...)` to format each event into one log line

Using the same renderer keeps CLI and Streamlit aligned semantically, even if styling differs.

## Request model

The streaming API request should mirror the workflow input shape closely.

Fields:

- `customer_profile_text`
- `meeting_note_text`
- `database_path`
- `execution_mode`
- `api_base_url` optional if the server needs to override provider routing
- `api_model` optional

Version 1 should keep the request minimal and avoid optional features such as pre-seeded summaries unless already needed by the app.

## Response/event model

The API should emit the same event family already defined by the workflow stream:

- `workflow_started`
- `node_started`
- `content_delta`
- `tool_call_delta`
- `tool_call_finished`
- `message_finished`
- `state_patch`
- `node_finished`
- `workflow_finished`
- `error`

The API layer should not rename events.

## File layout

### New files

- `D:\minimind\.worktrees\minimind-job-agent\sales_copilot\stream_api.py`
  - request model
  - SSE endpoint registration helper or FastAPI app/router factory
- `D:\minimind\.worktrees\minimind-job-agent\scripts\run_sales_copilot_stream_api.py`
  - runnable API entrypoint for local development

### Modified files

- `D:\minimind\.worktrees\minimind-job-agent\scripts\sales_copilot_web_demo.py`
  - add streaming API URL input
  - swap workflow invocation to SSE consumption path when streaming is enabled
  - render single continuous log area during execution
- `D:\minimind\.worktrees\minimind-job-agent\sales_copilot\stream_sse.py`
  - extend helper functions only if needed for app-facing transport
- `D:\minimind\.worktrees\minimind-job-agent\sales_copilot\stream_cli.py`
  - keep or lightly extend event rendering for log-friendly app display

## API design details

### FastAPI route

Recommend a dedicated small FastAPI app or router instead of mixing this into the OpenAI-compatible server.

Reason:

- the OpenAI-compatible API serves a different purpose
- Sales Copilot workflow streaming is an application workflow, not a generic chat-completions endpoint
- keeping them separate makes local development and later deployment cleaner

### Streaming response

Use `StreamingResponse` with `media_type="text/event-stream"`.

The route should:

1. build the workflow generator
2. wrap it through the SSE encoder
3. yield frames progressively

If an exception occurs:

- emit an `error` event if possible
- end the stream cleanly

## Streamlit design details

### Control flow

When Run is pressed:

1. clear previous live log state
2. open the HTTP stream
3. append each decoded event to a log buffer
4. rerender the log box as text grows
5. capture the final workflow result from `workflow_finished`
6. render the existing dashboard/CRM/task views from that final result

### Log rendering

The log area should be a single continuous stream, not separate per-node panes.

Formatting rules:

- `node_started` and `node_finished` should stand out as markers
- `content_delta` should append in place as normal text
- `tool_call_finished` should add one readable line
- `state_patch` should be summarized rather than dumping giant JSON blobs in full unless short

The app should stay readable even for long runs.

## Compatibility requirements

- non-streaming Streamlit usage should still be available as a fallback path if needed
- the existing workflow result rendering should remain unchanged once the final state is available
- CLI streaming behavior should remain valid and independent

## Testing plan

We need three test layers.

### API tests

- request validation works
- SSE route emits expected event types
- a successful run ends with `workflow_finished`

### Streamlit-adjacent tests

- parsing SSE payloads into event dicts works
- event log formatting is stable
- final result extraction from `workflow_finished` works

### Regression tests

- final workflow result returned through the app path matches the non-streaming workflow result for the same fake LLM input

## Success criteria

Version 1 is successful when:

- a local Sales Copilot streaming API can be started
- the Streamlit demo can consume it
- users can watch a single continuous real-time log during execution
- the final dashboard appears after stream completion
- final business output matches the existing workflow output for the same input

## Recommendation

Build a dedicated Sales Copilot SSE API on top of the shared workflow event generator, then make Streamlit consume that API and render a single live log. This preserves one execution core, gives us a real app-facing transport, and keeps future frontend integration straightforward.
