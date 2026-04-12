# Sales Copilot Task Candidates Design

## Summary

Add a lightweight `task_candidates` middle layer to Sales Copilot so task generation is driven more by concrete actions already present in the meeting context and less by generic sales follow-up templates.

The first version will:

- build deterministic `task_candidates` after lead evaluation
- source candidates from structured meeting signals rather than free-form generation
- pass candidates into the follow-up planning prompt
- merge candidate-derived tasks back into the final `task_payload`

This is a targeted improvement to the existing `baseline + RAG` mainline. It does not change the external workflow schema and does not revive the broader second-stage parse refinement experiments.

## Problem

On the new artificial sales workflow benchmark, RAG produces small positive movement for CRM usability, but generated tasks are still weak:

- too generic
- too detached from the actual meeting note
- too often centered on qualification-template actions rather than the specific follow-up that was actually discussed

Today, task generation is mostly driven by:

- a free-form follow-up planning prompt
- generic missing-information supplements such as:
  - `Confirm budget range`
  - `Confirm decision timeline`
  - `Identify decision makers`

That keeps the workflow structurally valid, but it often underuses the most valuable signal already available in the meeting summary:

- agreed next steps
- concrete deliverables
- customer follow-up asks
- risk-triggered prep actions

## Goals

- Make task generation more specific and evidence-grounded.
- Reuse concrete actions already present in the workflow state.
- Improve task quality without redesigning the overall workflow.
- Preserve compatibility with:
  - existing dashboard output
  - CRM writeback logic
  - workflow quality judge
- Keep the first version deterministic and easy to debug.

## Non-Goals

- Do not redesign the parse schema.
- Do not replace the current follow-up planning node with a fully new agent.
- Do not introduce a new free-form LLM task-generation stage before follow-up planning.
- Do not add a new external output schema for tasks.
- Do not change retrieval or RAG routing logic in this phase.

## Design

### New State Field

Add a new workflow state field:

- `task_candidates: list[dict[str, Any]]`

This is an internal-only field. It should not become a required external API contract.

### Candidate Shape

Each candidate should be a lightweight structured action:

```json
{
  "text": "schedule technical deep-dive next week",
  "source": "meeting_next_steps",
  "task_type": "customer_meeting",
  "priority_hint": "high",
  "timing_hint": "next_week",
  "evidence": ["Customer asked for a technical deep-dive next week."]
}
```

Required fields:

- `text`
- `source`
- `task_type`
- `priority_hint`
- `timing_hint`
- `evidence`

### Candidate Sources

The first version should stay narrow and deterministic.

Primary sources:

1. `meeting_summary.next_steps`
2. `meeting_summary.confirmed_needs` when the need clearly implies an executable follow-up, such as:
   - proposal
   - pricing
   - demo
   - security review
   - integration review
3. `risk_flags` when a risk implies a concrete mitigation action

The first version should not depend on a separate LLM call to propose candidates.

### Candidate Typing

Use a small controlled `task_type` vocabulary:

- `customer_follow_up`
- `customer_meeting`
- `internal_prep`
- `proposal_or_quote`
- `risk_mitigation`

The goal is not to perfectly taxonomize every action. The goal is to provide enough structure so downstream task generation can produce better titles and descriptions.

### Candidate Timing

The first version should infer a lightweight `timing_hint` from obvious language:

- `today`
- `this_week`
- `next_week`
- `this_month`
- `this_quarter`
- `unspecified`

This timing hint is only advisory. It should not replace existing due-date generation rules entirely.

### Workflow Placement

Add a new node after `evaluate_lead` and before route branching:

`evaluate_lead -> build_task_candidates -> route_after_lead_evaluation`

This keeps task-candidate construction centralized and route-agnostic.

### Prompt Changes

Update follow-up planning so the model is explicitly told:

- prioritize `task_candidates`
- operationalize agreed actions already present in the meeting
- avoid inventing generic qualification tasks when concrete actions already exist
- only add generic tasks if candidates are insufficient

The prompt should frame the job as:

`turn candidate follow-up actions into a concise execution plan`

not:

`invent tasks from scratch`

### Merge Logic

Task candidates should influence final tasks in two ways:

1. `prompt guidance`
   - the model sees the candidates directly

2. `post-generation merge`
   - candidate-derived tasks are converted into task payloads and merged with model tasks

This second layer is important because it reduces the chance that the model ignores candidates and falls back to generic templates.

### Route Behavior

All routes may carry `task_candidates`, but the strongest impact is expected on:

- `standard_follow_up`
- `high_priority_follow_up`

For:

- `need_more_info`
- `low_priority_nurture`

the existing generic supplementation logic remains useful and should stay in place. Candidate-derived tasks should complement, not replace, the current missing-facts fallback.

## File Changes

### New File

- `sales_copilot/task_candidates.py`

Responsibility:

- build task candidates from workflow state
- infer lightweight type and timing hints
- materialize candidate-derived tasks

### Existing Files

- `sales_copilot/state.py`
  - add `task_candidates`
- `sales_copilot/prompts.py`
  - update follow-up prompt builder to accept and describe task candidates
- `sales_copilot/graph.py`
  - add `build_task_candidates_node`
  - wire node into the graph
  - merge candidate-derived tasks into final payload
- `tests/sales_copilot/test_task_candidates.py`
  - new unit tests
- `tests/sales_copilot/test_prompts.py`
  - prompt contract tests
- `tests/sales_copilot/test_graph.py`
  - workflow integration tests

## Expected Outcome

After this change, final generated tasks should:

- more often reflect concrete meeting actions
- become less templated
- carry titles and descriptions closer to the benchmark's expected next actions

The most important evaluation target is not parse metrics. It is:

- workflow-quality judge scores on the artificial sales benchmark

especially:

- `task_structure_correctness_avg`
- `task_execution_quality_avg`
- `overall_score_avg`

## Risks

### Risk 1: Candidate Over-Merging

If every candidate is blindly turned into a task, the system may create too many tasks.

Mitigation:

- dedupe aggressively
- cap final task count through the existing prompt/output structure

### Risk 2: Generic Needs Become Forced Tasks

Some confirmed needs describe interest, not action.

Mitigation:

- only promote needs that clearly imply executable follow-up

### Risk 3: Need-More-Info Cases Still Need Generic Tasks

Purely concrete candidate-driven tasks may miss qualification gaps.

Mitigation:

- preserve missing-facts supplementation

## Success Criteria

This design is successful if:

- the workflow remains schema-compatible
- the new node is deterministic and testable
- tasks on the artificial sales benchmark become more specific
- workflow quality judge scores improve mainly on task dimensions, without harming CRM usability
