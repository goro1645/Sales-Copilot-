# Sales Copilot MCP CRM Design Spec

## Summary

Add a minimal but real MCP-backed tool layer to `Sales Copilot` so the project can demonstrate `LangGraph + Tool Use + MCP` in a way that is technically honest and easy to run locally.

The first version should expose only CRM and task operations through MCP, while keeping the existing direct SQLite path as a fallback. This keeps the current project stable and makes the MCP integration easy to explain in interviews.

## Goals

- add a real local MCP server for CRM and task operations
- keep the existing `direct storage` path working
- let `Sales Copilot` run in either `direct` mode or `mcp` mode
- make `write_back_crm` and task persistence capable of going through MCP
- support offline evaluation in `mcp` mode
- produce resume-safe metrics such as workflow success rate, CRM write-back accuracy, task generation hit rate, and MCP tool success rate

## Non-Goals

- moving all retrieval tools to MCP in V1
- moving memory loading to MCP in V1
- integrating a real external SaaS CRM
- distributed MCP deployment
- authentication or multi-user tenancy

## Why This Scope

The current project already has:

- local SQLite persistence for `accounts`, `meeting_records`, `tasks`, and `crm_updates`
- a working `LangGraph` workflow
- a local demo UI
- an offline evaluation stack

Because these pieces already exist, the most defensible first MCP integration is to wrap the existing CRM and task writes in an MCP server instead of redesigning the whole system.

This gives the project a real MCP story without destabilizing the rest of the stack.

## Approaches Considered

### Approach 1: Wrap Existing CRM And Tasks In A Local MCP Server

This approach adds a local MCP server and a thin client adapter while keeping the current direct code path intact.

Pros:

- smallest implementation surface
- preserves current working behavior
- easy to test
- easy to explain in an interview

Cons:

- retrieval and memory are still direct in V1

### Approach 2: Move CRM, Tasks, And Retrieval To MCP

This would make MCP more central to the architecture.

Pros:

- stronger architecture story
- broader MCP coverage

Cons:

- much higher risk
- larger integration surface
- likely to slow down evaluation work

### Approach 3: Mock MCP Without A Real Running Server

This would implement interface shapes only.

Pros:

- fastest

Cons:

- weaker technical credibility
- easier for an interviewer to challenge

### Recommendation

Use Approach 1.

It adds a real MCP server, keeps the system runnable, and is the best tradeoff between engineering value and implementation risk.

## Architecture

### Existing Pieces To Keep

- [sales_copilot/storage.py](D:/minimind/.worktrees/minimind-job-agent/sales_copilot/storage.py)
- [sales_copilot/tools.py](D:/minimind/.worktrees/minimind-job-agent/sales_copilot/tools.py)
- [sales_copilot/graph.py](D:/minimind/.worktrees/minimind-job-agent/sales_copilot/graph.py)
- [sales_copilot/runner.py](D:/minimind/.worktrees/minimind-job-agent/sales_copilot/runner.py)
- [sales_copilot_web_demo.py](D:/minimind/.worktrees/minimind-job-agent/scripts/sales_copilot_web_demo.py)
- [run_sales_copilot_eval.py](D:/minimind/.worktrees/minimind-job-agent/scripts/run_sales_copilot_eval.py)

### New Components

- `sales_copilot/mcp_server.py`
  - starts a local MCP server
  - exposes CRM and task tools
  - delegates to existing storage helpers

- `sales_copilot/mcp_client.py`
  - wraps MCP tool calls for the workflow
  - gives the graph a small, stable interface

### Execution Modes

The workflow should support two modes:

- `direct`
  - current behavior
  - direct calls into storage and tools

- `mcp`
  - write-side CRM and task operations go through MCP

Mode selection should be explicit in runner and demo entrypoints.

## MCP Tool Surface

V1 should expose exactly four tools.

### `get_account`

Input:

- `account_id`

Output:

- account id
- account name
- status
- opportunity stage
- last contact timestamp

### `list_account_tasks`

Input:

- `account_id`
- optional `status`

Output:

- task list for that account

### `create_task`

Input:

- `account_id`
- `meeting_id`
- `title`
- `description`
- `priority`
- `due_at`
- optional `status`

Output:

- `task_id`

### `update_account_stage`

Input:

- `account_id`
- `status`
- `opportunity_stage`
- `last_contact_at`

Output:

- updated account state

## Workflow Integration

### What Changes In V1

Only the write-back stage should move to MCP.

Specifically, the `write_back_crm` node in [graph.py](D:/minimind/.worktrees/minimind-job-agent/sales_copilot/graph.py) should:

- continue to resolve account and meeting ids as it does today
- when in `direct` mode, preserve current behavior
- when in `mcp` mode:
  - use MCP to read current account state if needed
  - use MCP to create tasks
  - use MCP to update account stage/status

The system should still persist `crm_updates` and `meeting_records` locally. V1 is not trying to make every write path remote. The point is to demonstrate a real MCP-backed enterprise tool boundary while preserving current storage semantics.

## Data Flow

### Direct Mode

1. parse notes
2. retrieve context
3. load memory
4. evaluate lead
5. route to follow-up branch
6. write CRM and tasks directly
7. render dashboard

### MCP Mode

1. parse notes
2. retrieve context
3. load memory
4. evaluate lead
5. route to follow-up branch
6. call MCP tools for CRM/task actions
7. persist local workflow outputs that are still local in V1
8. render dashboard

## Error Handling

### MCP Server Errors

If an MCP tool call fails:

- the workflow should mark the run as failed for evaluation purposes
- the UI should show a clear error
- the exception should not be silently swallowed

### Unsupported Mode

If the caller requests an unknown mode, the runner should raise a clear `ValueError`.

### Server Availability

If `mcp` mode is selected and the MCP server is not reachable:

- fail fast with a clear startup or call-time error
- do not silently fall back to `direct`

Silent fallback would make the MCP claim weaker and make debugging harder.

## Testing Strategy

### Unit Tests

Add focused tests for:

- MCP server tool handlers
- MCP client request/response handling
- invalid input behavior

### Workflow Integration Tests

Add tests showing:

- `mcp` mode creates tasks successfully
- `mcp` mode updates account stage successfully
- repeated runs do not create broken or duplicate write-back behavior beyond current intended semantics

### Evaluation Regression

Extend the offline evaluation runner so it can run in `mcp` mode and verify:

- workflow success rate
- CRM write-back accuracy
- task generation hit rate

## Evaluation Metrics To Report

The project should report only metrics it can actually compute locally.

Recommended V1 metrics:

- `workflow_success_rate`
- `crm_writeback_accuracy`
- `task_generation_hit_rate`
- `required_task_hit_rate`
- `mcp_tool_success_rate`
- optional `direct_vs_mcp_consistency_rate`

Do not claim:

- real production latency
- real enterprise traffic success rates
- real customer data performance

## Files To Add

- `sales_copilot/mcp_server.py`
- `sales_copilot/mcp_client.py`
- `tests/sales_copilot/test_mcp_server.py`
- `tests/sales_copilot/test_mcp_client.py`

## Files To Modify

- [sales_copilot/graph.py](D:/minimind/.worktrees/minimind-job-agent/sales_copilot/graph.py)
- [sales_copilot/runner.py](D:/minimind/.worktrees/minimind-job-agent/sales_copilot/runner.py)
- [sales_copilot_web_demo.py](D:/minimind/.worktrees/minimind-job-agent/scripts/sales_copilot_web_demo.py)
- [run_sales_copilot_eval.py](D:/minimind/.worktrees/minimind-job-agent/scripts/run_sales_copilot_eval.py)
- evaluation tests as needed

## Demo Expectations

The demo should let the user choose:

- `direct`
- `mcp`

In `mcp` mode, a successful run should still show:

- lead score
- priority
- stage
- CRM write-back preview
- generated tasks
- workflow log

The difference is that CRM/task actions are executed through MCP rather than direct local calls.

## Resume-Safe Project Framing

After this is implemented, the project can honestly be described as:

`Built a LangGraph-based sales workflow agent with MCP-backed CRM and task tool integration, supporting both direct and MCP execution modes and validated through local offline evaluation.`

## Risks

- local MCP runtime details may vary depending on installed packages
- adding MCP too deeply into the graph would increase scope and integration risk
- mixing direct and MCP semantics carelessly could create inconsistent write-back behavior

## Mitigations

- keep MCP scope limited to CRM and tasks in V1
- keep direct mode intact as a known-good baseline
- add direct-vs-mcp regression coverage for the same sample cases
- fail fast when MCP mode is selected but server connectivity is missing

## Success Criteria

This design is successful when:

- `Sales Copilot` can run in both `direct` and `mcp` mode
- CRM and task writes can flow through a real local MCP server
- offline evaluation can run against `mcp` mode
- the project can report real local MCP-related metrics
- the MCP story is technically honest and easy to demonstrate
