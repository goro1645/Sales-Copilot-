# Sales Copilot Workflow-Calibrated Benchmark Design

## Summary

Build a new `workflow-calibrated-30` benchmark for Sales Copilot that evaluates the final business outcomes of the workflow rather than only parse quality. The benchmark will contain 30 workflow cases sourced from `AI-calibrated 100 / full-CSDS`-derived material, and each case will include an AI-calibrated final draft for:

- CRM writeback expectations
- Task generation expectations
- Acceptable variants and evidence

This benchmark is intended to answer questions that current workflow metrics do not answer well, especially:

- Is the CRM writeback correct and useful?
- Are generated tasks actionable and reasonable?
- Does RAG improve final workflow quality, not just intermediate scoring?

This is an `AI-calibrated benchmark draft`, not a human-verified gold benchmark.

## Problem

Current workflow evaluation is too coarse. It checks:

- whether CRM was written back
- whether tasks were generated
- whether required task titles were hit

It does not check:

- whether the CRM payload is semantically correct
- whether the selected stage/status/risk flags are appropriate
- whether the recommended next step is good
- whether task descriptions, owners, priorities, and timing are actionable

As a result, the project can compare workflow branches structurally, but it still lacks a benchmark for the final quality of business-facing outputs.

## Goals

- Create a realistic workflow benchmark focused on final output quality.
- Cover all major workflow routes:
  - `high_priority_follow_up`
  - `standard_follow_up`
  - `low_priority_nurture`
  - `need_more_info`
- Use more realistic sample sources than the handcrafted golden workflow set.
- Support future A/B comparisons such as:
  - baseline vs RAG
  - baseline vs second-stage refinement
  - direct vs MCP execution

## Non-Goals

- Do not replace the existing `golden_cases.jsonl` workflow benchmark.
- Do not claim this dataset is fully human-calibrated.
- Do not redesign the main workflow in this phase.
- Do not implement a judge model in this phase.

## Dataset Scope

### Size

The benchmark will contain exactly `30` cases.

### Source

Cases will be selected from the pool already available through:

- `full_csds_ai_calibrated_100.jsonl`
- its source working set and related CSDS-derived materials when needed for context

The source should be treated as the upstream realistic dataset pool. The final benchmark is a new workflow-oriented subset, not a direct reuse of existing parse-only benchmark entries.

### Distribution

The 30 cases should be approximately balanced across workflow routes:

- `8` high-priority follow-up cases
- `8` standard follow-up cases
- `7` low-priority nurture cases
- `7` need-more-info cases

If the source pool cannot satisfy an exact bucket count, the builder may rebalance slightly while preserving broad route coverage.

## Case Format

The final benchmark will be stored as a single JSONL file. Each row will include the original workflow inputs plus a workflow-calibrated expected output section.

### Top-Level Fields

Each case should contain:

- `case_id`
- `source_case_id`
- `source_dataset`
- `segment`
- `customer_profile_text`
- `meeting_note_text`
- `expected_parse`
- `expected_workflow`
- `calibration_note`

### `expected_workflow`

The workflow expectation object should include:

- `lead_score_range`
- `lead_priority`
- `opportunity_stage`
- `expected_route`
- `expected_crm_writeback`
- `expected_task_bundle`

### `expected_crm_writeback`

This object should include:

- `should_write`
- `account_status`
- `opportunity_stage`
- `risk_flags`
- `recommended_next_step`
- `evidence`
- `acceptable_variants`

Field guidance:

- `should_write` is a boolean indicating whether CRM writeback is expected.
- `account_status` is the intended account state after workflow completion.
- `opportunity_stage` is the intended CRM stage after workflow completion.
- `risk_flags` is the expected set of high-signal workflow risk labels.
- `recommended_next_step` is the expected next action summary written to CRM memory/state.
- `evidence` is a short list of source-grounded reasons supporting the expected CRM update.
- `acceptable_variants` is a list of allowed alternative phrasings or equally acceptable CRM outcomes.

### `expected_task_bundle`

This object should include:

- `should_generate`
- `tasks`
- `acceptable_variants`

Each task object should include:

- `title`
- `description`
- `priority`
- `owner`
- `timing_expectation`
- `evidence`

Field guidance:

- `should_generate` is a boolean.
- `tasks` is the canonical expected set of tasks.
- `acceptable_variants` captures alternative but acceptable task bundles.
- `timing_expectation` is a textual expectation such as `same_day`, `next_day`, `within_week`, or a short natural-language timing description.

## Calibration Policy

The benchmark is AI-calibrated, meaning the assistant will directly produce the final expected workflow draft instead of generating a working file that requires human review before export.

This benchmark must therefore be labeled consistently as:

- `AI-calibrated workflow benchmark draft`

It must not be labeled as:

- `human-calibrated`
- `fully human-verified`
- `gold-standard`

## Drafting Heuristics

The final expected workflow outputs should be calibrated using:

- original case text
- upstream expected parse when useful
- realistic business interpretation of CRM writeback
- realistic task execution standards

When drafting expected CRM and task outputs:

- prefer actionable business outcomes over brittle string-level exactness
- allow concise acceptable variants where wording may differ but intent is equivalent
- avoid requiring overly specific wording that would punish reasonable paraphrases
- keep evidence grounded in the source note/profile rather than external invention

## Evaluation Intent

This benchmark is designed to support future richer workflow evaluation, including:

- CRM writeback presence and quality
- task generation presence and quality
- route and stage correctness
- evidence-grounded final actionability

This benchmark does not itself define the full scoring implementation. It defines the benchmark structure and the expectations required for that later scoring layer.

## Deliverables

This work should produce:

- a final benchmark JSONL file containing 30 workflow-calibrated cases
- a Markdown field guide explaining the benchmark schema and interpretation

Recommended output paths:

- `evals/sales_copilot/full_csds_workflow_calibrated_30.jsonl`
- `evals/sales_copilot/full_csds_workflow_calibrated_30_README.md`

If project conventions require generated artifacts to live under an outputs directory first, the implementation may stage them there before promoting the stable benchmark file into the main evals path.

## Success Criteria

This design is successful if:

- the dataset contains 30 realistic workflow cases
- all four workflow routes are represented
- every case includes complete CRM writeback and task bundle expectations
- the resulting benchmark is usable for future baseline vs RAG workflow comparisons
- the benchmark is clearly labeled as AI-calibrated draft rather than human gold

## Risks

- AI-calibrated expectations may still reflect model bias or current system style.
- Some source cases may not contain enough evidence to justify fully rich CRM/task expectations.
- Over-specifying acceptable outputs may make future evaluation brittle.

## Mitigations

- include acceptable variants for CRM and task outputs
- keep evidence lists concise and grounded
- prefer route-balanced, representative cases rather than only hard cases
- treat this benchmark as a draft evaluation layer, not final truth

