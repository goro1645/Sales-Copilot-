# Sales Copilot Streaming Design

## Goal

Add a single streaming model for Sales Copilot that works in both:

- CLI / evaluation scripts with real-time terminal output
- application-facing interfaces via structured events and SSE wrappers

The design should preserve the current non-streaming workflow and add a parallel streaming path rather than replacing the existing code.

## Why this matters

We already have provider-level streaming support in `DeepSeekClient.stream(...)`, including token deltas and tool-call assembly. What is missing is an end-to-end workflow-level streaming abstraction. Right now:

- the workflow runs as a black box
- CLI runs only print final outputs
- app integrations cannot observe node progress or tool-call progress in real time

This design closes that gap with one shared event model.

## Scope

First version covers:

- structured workflow events
- streaming for LLM-driven nodes
- CLI real-time rendering
- application-facing SSE wrapper built on the same generator contract

First version does **not** attempt to stream every low-level operation such as SQLite writes or every retrieval sub-step as token-like deltas. Non-LLM steps should emit start / finish status events only.

## Event model

The streaming core emits dictionaries with a stable `type` field. First version supports:

- `workflow_started`
- `workflow_finished`
- `node_started`
- `node_finished`
- `content_delta`
- `tool_call_delta`
- `tool_call_finished`
- `message_finished`
- `state_patch`
- `error`

### Event semantics

#### `workflow_started`

Emitted once at the beginning of a run.

Fields:

- `type`
- `workflow_name`
- `execution_mode`

#### `node_started`

Emitted when a workflow node begins.

Fields:

- `type`
- `node`
- `streaming`

`streaming` indicates whether the node is expected to emit token/tool-call events.

#### `content_delta`

Provider text token or chunk.

Fields:

- `type`
- `node`
- `text`

#### `tool_call_delta`

Incremental tool-call assembly event from the provider stream.

Fields:

- `type`
- `node`
- `index`
- `id`
- `name`
- `arguments_delta`

#### `tool_call_finished`

Completed tool-call payload.

Fields:

- `type`
- `node`
- `index`
- `id`
- `name`
- `arguments`

#### `message_finished`

Marks end of one model response.

Fields:

- `type`
- `node`
- `finish_reason`

#### `state_patch`

Structured non-token result from a node.

Fields:

- `type`
- `node`
- `patch`

Used when a node completes and produces updated state fields such as:

- `meeting_summary`
- `lead_priority`
- `opportunity_stage`
- `task_candidates`
- `task_payload`

#### `node_finished`

Emitted after a node completes successfully.

Fields:

- `type`
- `node`

#### `workflow_finished`

Emitted once with final result.

Fields:

- `type`
- `result`

#### `error`

Emitted when the workflow fails.

Fields:

- `type`
- `node`
- `message`

## Execution model

### Non-streaming path

Keep the current `run_sales_copilot(...)` path unchanged for compatibility.

### Streaming path

Add a parallel entry point:

- `run_sales_copilot_stream(...)`

This function returns a Python generator of structured events.

The generator should:

1. emit `workflow_started`
2. execute nodes in order
3. emit `node_started`
4. for LLM nodes, consume `llm_client.stream(...)`
5. emit token and tool-call events as they arrive
6. finalize node output into the same state shape used by non-streaming execution
7. emit `state_patch` and `node_finished`
8. emit `workflow_finished` with the final state

If any error occurs, emit `error` and re-raise or stop depending on the caller contract.

## Node coverage in v1

### Streaming LLM nodes

These should emit token/tool-call events:

- `parse_meeting_note`
- `evaluate_lead`
- `generate_followup_plan`
- workflow quality judge nodes

### Non-streaming nodes with status events only

These emit only `node_started`, optional `state_patch`, and `node_finished`:

- retrieval/context loading
- task candidate building
- account memory loading
- CRM writeback
- task persistence

## Parsing streamed LLM output

We should reuse `DeepSeekClient.stream(...)` as the provider-facing primitive.

For JSON-producing nodes, the workflow streaming layer should:

- collect `content_delta` chunks into a local buffer
- emit the deltas immediately for observers
- at `message_finished`, parse the accumulated text into the same JSON payload shape currently consumed by non-streaming code

For tool-call capable nodes, the workflow layer should:

- forward `tool_call_delta` and `tool_call_finished`
- when needed, consume the assembled tool payload exactly as current code does in non-streaming mode

## CLI integration

Add `--stream` support to the relevant scripts and render the shared event stream in terminal-friendly form.

Expected behavior:

- print node banners on `node_started`
- print live text on `content_delta`
- print concise tool-call updates on `tool_call_finished`
- print summarized patches on `state_patch`
- print final report paths and summary on `workflow_finished`

The CLI should be a renderer only. It must not implement workflow logic that diverges from the core generator.

## SSE integration

Add an application-facing wrapper that converts the same event generator into SSE frames.

Recommended first wrapper:

- `stream_sales_copilot_sse(...)`

This wrapper should:

- iterate the Python generator
- serialize each event as JSON
- emit SSE frames with event names matching the event `type`

This keeps the streaming contract unified:

- core workflow owns event production
- CLI renders events to text
- app layer renders events to SSE

## File layout changes

Expected changes:

- `sales_copilot/runner.py`
  - add `run_sales_copilot_stream(...)`
- `sales_copilot/graph.py`
  - expose or refactor node execution so streaming and non-streaming paths can share logic
- `llm/deepseek_client.py`
  - keep current provider streaming, only extend if small fixes are needed
- `sales_copilot/streaming.py` or equivalent new module
  - workflow event helpers / stream execution helpers
- CLI scripts
  - add `--stream`
- app or API layer
  - add SSE wrapper

## Compatibility requirements

- existing non-streaming APIs must keep working
- tests for current non-streaming behavior must continue to pass
- streaming code should not change final business outputs relative to non-streaming mode for the same inputs

## Testing plan

We need three layers of tests.

### Unit tests

- provider stream events are forwarded and normalized correctly
- streamed JSON accumulation reconstructs the final payload correctly
- tool-call deltas assemble into finished tool-call events correctly

### Workflow tests

- `run_sales_copilot_stream(...)` emits the expected event order
- final result from streaming matches non-streaming run
- non-LLM nodes emit started/finished events even without token deltas

### CLI / SSE tests

- `--stream` mode prints real-time output without crashing
- SSE wrapper yields valid event frames with JSON payloads

## Success criteria

First version is successful when:

- we can run the main Sales Copilot workflow in streaming mode from CLI
- we can observe token/tool-call progress for LLM nodes
- final state matches current non-streaming output
- the same event stream can be exposed through an SSE wrapper

## Non-goals for v1

- full observability for every storage or retrieval micro-step
- redesigning LangGraph around native streaming primitives
- replacing all existing scripts with SSE-first transport

## Recommendation

Implement the streaming system as a shared workflow event generator with two renderers:

- CLI renderer for terminal use
- SSE renderer for app use

This gives us one event model, avoids duplicate business logic, and fits the current codebase because provider-level streaming already exists.
