# Sales Copilot Artificial Sales Workflow Benchmark Design

## Summary

Build a new `artificial-sales-workflow-50` benchmark for Sales Copilot that is intentionally written for the product's target workflow rather than adapted from customer-service corpora.

The benchmark will contain `50` AI-authored but workflow-grounded cases focused on ecommerce merchant and platform sales scenarios. Each case will include:

- realistic `customer_profile_text`
- meeting-note-first workflow inputs
- parse expectations
- full workflow expectations for:
  - route
  - CRM writeback
  - task generation

This benchmark is meant to answer questions that the current CSDS-derived sets cannot answer well:

- Does the workflow handle true sales follow-up scenarios well?
- Does RAG help when the case actually needs sales knowledge rather than customer-service policy knowledge?
- Are CRM writeback and generated tasks good for sales execution, not just structurally present?

This is an `AI-authored benchmark draft`, not a human-verified gold benchmark.

## Problem

Current benchmark layers leave an important gap:

- `full-CSDS 800` is useful for large-scale regression tracking but is a weak benchmark adapted from customer-service summaries
- `AI-calibrated 100` is more reviewable, but still anchored in a customer-service-heavy source pool
- `workflow-calibrated 30` is useful for judging final CRM/task quality, but it inherits customer-service route skew from its source data

As a result, the project still lacks a benchmark centered on the target product behavior:

- ecommerce merchant or platform sales qualification
- solution discovery
- objection handling
- commercial follow-up
- opportunity advancement
- low-intent nurture when there is real sales ambiguity rather than pure after-sales support

This prevents clean evaluation of whether the system is good at sales workflow execution, especially for:

- route selection
- CRM stage and risk updates
- recommended next steps
- actionability of generated tasks
- RAG value for sales-oriented reasoning

## Goals

- Create a realistic but fully controlled benchmark focused on ecommerce merchant and platform sales workflows.
- Cover the full sales funnel rather than only customer-service scenarios.
- Make the benchmark suitable for:
  - baseline workflow evaluation
  - with-RAG vs without-RAG A/B tests
  - future CRM/task quality judge evaluation
- Preserve compatibility with the existing Sales Copilot evaluation pipeline.
- Use meeting-note-first inputs so the dataset fits the current system interface naturally.

## Non-Goals

- Do not replace CSDS-derived benchmarks.
- Do not claim this benchmark is real-world observational data.
- Do not present this benchmark as human-calibrated.
- Do not redesign the core Sales Copilot workflow in this phase.
- Do not implement the evaluation runner in this design phase.

## Dataset Positioning

This benchmark should be positioned as:

- `AI-authored workflow benchmark draft`
- `target-domain benchmark for sales workflow evaluation`

It must not be positioned as:

- `human-calibrated benchmark`
- `public real-world dataset`
- `gold-standard benchmark`

Recommended internal role:

- CSDS-based benchmarks continue to answer "how does the system behave on realistic customer-service-style language?"
- this benchmark answers "how does the system behave on the product's intended sales workflow?"

## Dataset Scope

### Size

The benchmark contains exactly `50` cases.

### Domain

The domain is:

- ecommerce merchant and platform sales

Representative themes include:

- merchant onboarding interest
- store operation tooling
- CRM or order integration
- private deployment and compliance needs
- team collaboration and permission management
- reporting and audit visibility
- campaign operations and follow-up automation
- objections about budget, implementation effort, or unclear ROI

### Input Style

Cases should use a hybrid input style:

- primarily meeting-note format
- with light traces of real dialogue style where useful

This means each case should read like a realistic internal sales note rather than a polished benchmark sentence list.

### Funnel Coverage

The 50 cases should be distributed across five funnel phases:

- `10` initial contact / lead judgment
- `10` need discovery / qualification
- `10` solution evaluation / objection handling
- `10` pricing or deal progression / next-step push
- `10` low-intent, deferred, or nurture situations

### Route Distribution

The benchmark should be intentionally sales-forward:

- `15` `high_priority_follow_up`
- `15` `standard_follow_up`
- `10` `need_more_info`
- `10` `low_priority_nurture`

This is deliberately different from the CSDS-derived workflow benchmark, which over-represents customer-service-like low-intent routes.

## Knowledge Assumptions

This benchmark should be authored assuming a mixed knowledge environment rather than a single sales-playbook source.

The intended knowledge backdrop includes:

- product capability documents
- merchant or platform rules and operating guidance
- sales playbook knowledge

This matters because later RAG comparisons should test whether the system uses the right type of knowledge, not only whether any retrieved text was present.

## Case Format

The final benchmark should be stored as a single JSONL file.

Each row should contain:

- `case_id`
- `source_case_type`
- `segment`
- `customer_profile_text`
- `meeting_note_text`
- `expected_parse`
- `expected_workflow`
- `author_note`

### `source_case_type`

Because this benchmark is authored rather than sampled from a public corpus, `source_case_type` should describe the authored scenario family, for example:

- `merchant_onboarding`
- `integration_interest`
- `compliance_objection`
- `budget_pushback`
- `stalled_nurture`

### `expected_parse`

`expected_parse` should stay compatible with the current parse evaluation schema, including:

- `account_name`
- `customer_roles`
- `confirmed_needs`
- `objections`
- `next_steps`
- `budget_signals`
- `timeline_signals`
- `competitors`

The parse expectation should be realistic and concise, not overfit to any exact prompt style.

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

- `should_write`: whether CRM should be updated
- `account_status`: intended account state after processing
- `opportunity_stage`: intended CRM opportunity stage
- `risk_flags`: high-signal workflow risks or blockers
- `recommended_next_step`: the main next action that should be written back
- `evidence`: concise reasons grounded in the note/profile
- `acceptable_variants`: valid alternative phrasings or equally acceptable CRM outcomes

### `expected_task_bundle`

This object should include:

- `should_generate`
- `tasks`
- `acceptable_variants`

Each task should include:

- `title`
- `description`
- `priority`
- `owner`
- `timing_expectation`
- `evidence`

Task expectations should prioritize executability over stylistic exactness.

## Authoring Policy

The benchmark should be authored directly as final-draft expectations rather than via a separate working-file review loop.

That means:

- the assistant directly writes the final draft
- the resulting dataset is still clearly labeled as AI-authored
- the benchmark is suitable for iteration and internal comparison, not for external claims of human-verified performance

## Case Authoring Heuristics

When authoring cases:

- keep scenarios plausible for ecommerce merchant and platform sales
- include enough detail to drive route, CRM, and task differences
- avoid perfect, unrealistic clarity in every case
- mix strong-intent and ambiguous-intent examples
- include realistic objections around:
  - cost
  - implementation effort
  - data migration
  - compliance
  - uncertainty about internal ownership
- include realistic momentum signals around:
  - confirmed stakeholder involvement
  - requested demo or proposal
  - timeline pressure
  - integration interest
  - operational pain

When authoring the note style:

- prefer operational realism over benchmark neatness
- let some notes contain partial information and mixed signals
- avoid writing all cases in the same voice

## Evaluation Intent

This benchmark is intended primarily for workflow-level evaluation, not only parse scoring.

The first intended uses are:

- baseline workflow evaluation
- with-RAG vs without-RAG comparison
- CRM writeback quality judging
- task generation quality judging

Parse evaluation may be run on the same cases, but workflow evaluation is the primary purpose.

## Deliverables

This work should ultimately produce:

- a benchmark JSONL file containing 50 authored workflow cases
- a Markdown field guide documenting schema, route distribution, and authoring assumptions

Recommended output paths:

- `evals/sales_copilot/artificial_sales_workflow_benchmark_50.jsonl`
- `evals/sales_copilot/artificial_sales_workflow_benchmark_50_README.md`

## Success Criteria

This design is successful if:

- the benchmark contains exactly 50 cases
- all four workflow routes are represented at the intended distribution
- cases cover the full intended sales funnel
- each case includes complete CRM and task expectations
- the benchmark can be used to test whether RAG helps on actual sales-style workflow cases
- the benchmark is clearly labeled as AI-authored draft rather than human gold

## Risks

- authored cases may overfit the current system's language or assumptions
- scenarios may become too clean and therefore easier than real notes
- route balance may accidentally reduce realism if every category is made too formulaic
- benchmark results could be misread as real-world generalization results

## Mitigations

- vary scenario structure and information completeness
- include ambiguous and mixed-signal cases, not only ideal clean cases
- keep acceptable variants for CRM and task outputs where wording naturally differs
- document the benchmark honestly as authored draft data for internal evaluation

