# Sales Copilot Offline Evaluation Design Spec

Date: 2026-04-04
Status: Draft approved in conversation, written for review
Project root: `D:\minimind\.worktrees\minimind-job-agent`

## 1. Goal

Add a repeatable offline evaluation stack for `Sales Copilot` so the project can produce real, local, resume-safe metrics instead of anecdotal demos.

The evaluation system must cover two layers:

- `parse-only evaluation`: measure how well meeting notes are converted into structured JSON
- `end-to-end workflow evaluation`: measure whether the full LangGraph workflow produces the expected routing, CRM actions, and follow-up tasks

The output must be suitable for:

- README and project documentation
- local regression checks after workflow changes
- interview discussions about evaluation methodology
- resume bullets with real metrics

## 2. Why This Version

This design uses a `local golden dataset + deterministic metrics` approach because it best matches the current project stage.

Reasons:

- It avoids depending on online judge models for core metrics.
- It produces stable numbers that can be re-run after code changes.
- It aligns with the current SQLite- and file-based architecture.
- It keeps metric definitions inspectable enough for interviews.

## 3. Scope

V1 includes:

- a `15 to 20` case golden dataset stored locally
- one schema that supports both parse and workflow expectations
- one runner that executes the full workflow on each case
- metric computation for extraction quality and workflow quality
- JSON and Markdown reports
- tests for metric logic and evaluation runner behavior

V1 does not include:

- LLM-as-a-judge scoring for subjective writing quality
- online benchmark dashboards
- distributed evaluation infrastructure
- statistical significance analysis
- production telemetry ingestion

## 4. Dataset Design

The golden dataset will live at:

- `evals/sales_copilot/golden_cases.jsonl`

Each line is one case with these top-level fields:

- `case_id`
- `segment`
- `customer_profile_text`
- `meeting_note_text`
- `expected_parse`
- `expected_workflow`

### 4.1 Segment Coverage

The dataset should cover four scenario buckets:

1. `high_intent_complete`
2. `high_intent_missing_facts`
3. `medium_intent_nurture`
4. `low_intent_or_noise`

Recommended distribution for the first version:

- 4 to 5 cases in `high_intent_complete`
- 4 to 5 cases in `high_intent_missing_facts`
- 4 to 5 cases in `medium_intent_nurture`
- 3 to 5 cases in `low_intent_or_noise`

### 4.2 Expected Parse Labels

`expected_parse` contains the ground-truth extraction targets for the fields the workflow actually consumes:

- `account_name`
- `customer_roles`
- `confirmed_needs`
- `budget_signals`
- `timeline_signals`
- `next_steps`
- `competitors`

These fields are enough to evaluate parse quality without overfitting the benchmark to every possible free-form note detail.

### 4.3 Expected Workflow Labels

`expected_workflow` contains the expected business outcome:

- `lead_score_range`
- `lead_priority`
- `opportunity_stage`
- `expected_route`
- `should_write_crm`
- `should_generate_tasks`
- `required_task_titles`
- `required_risk_flags`

`lead_score_range` is used instead of an exact score because LLM scoring is naturally noisy and the workflow only needs the score to be directionally correct.

## 5. Metrics

V1 metrics are split into `parse metrics` and `workflow metrics`.

### 5.1 Parse Metrics

Required metrics:

- `json_valid_rate`
- `field_exact_match_rate`
- `list_field_precision`
- `list_field_recall`
- `list_field_f1`
- `risk_flag_recall`

Interpretation:

- `json_valid_rate`: percentage of runs that produce parseable JSON
- `field_exact_match_rate`: exact match for scalar fields such as `account_name`
- `list_field_precision/recall/f1`: used for fields like `confirmed_needs`, `customer_roles`, and `competitors`
- `risk_flag_recall`: whether missing-fact or risk-style signals are captured when expected

### 5.2 Workflow Metrics

Required metrics:

- `workflow_success_rate`
- `route_accuracy`
- `priority_accuracy`
- `stage_accuracy`
- `score_range_accuracy`
- `crm_writeback_accuracy`
- `task_generation_hit_rate`
- `required_task_hit_rate`

Interpretation:

- `workflow_success_rate`: the run completed without exception and returned a full result
- `route_accuracy`: the workflow branch matched the expected route
- `priority_accuracy`: predicted priority matches the golden label
- `stage_accuracy`: predicted opportunity stage matches the golden label
- `score_range_accuracy`: returned score falls within the expected range
- `crm_writeback_accuracy`: write-back happened when it should and did not happen when it should not
- `task_generation_hit_rate`: tasks exist when a case requires tasks
- `required_task_hit_rate`: required follow-up tasks are present by keyword/title matching

## 6. Repository Layout

Add the evaluation stack under:

- `evals/sales_copilot/golden_cases.jsonl`
- `evals/sales_copilot/metrics.py`
- `evals/sales_copilot/runner.py`
- `evals/sales_copilot/reporting.py`
- `evals/sales_copilot/outputs/`
- `scripts/run_sales_copilot_eval.py`
- `tests/evals/test_sales_copilot_metrics.py`
- `tests/evals/test_sales_copilot_runner.py`

Responsibilities:

- `golden_cases.jsonl`: benchmark inputs and labels
- `metrics.py`: metric computation only
- `runner.py`: load cases, run workflow, collect raw per-case results
- `reporting.py`: write `report.json`, `report.md`, and per-case outputs
- `run_sales_copilot_eval.py`: CLI entrypoint
- tests: keep evaluation logic stable and regression-safe

## 7. Execution Model

The runner should execute each case in two logical passes:

1. `parse pass`
   - run the same parse path used by the workflow
   - compare output against `expected_parse`

2. `workflow pass`
   - call `run_sales_copilot(...)`
   - compare workflow outputs against `expected_workflow`

This separation is intentional:

- it makes failures diagnosable
- it distinguishes model extraction quality from workflow orchestration quality
- it provides better material for interviews and debugging

## 8. Output Artifacts

Each evaluation run should produce:

- `report.json`
- `report.md`
- `case_results.jsonl`

Recommended output directory:

- `evals/sales_copilot/outputs/<timestamp>/`

`report.md` should include:

- dataset size
- case distribution by segment
- parse metrics table
- workflow metrics table
- top failing cases with short explanations

## 9. Command Line Interface

The first CLI should support:

```powershell
& 'D:\anaconda\envs\minimind_job_agent\python.exe' `
  D:\minimind\.worktrees\minimind-job-agent\scripts\run_sales_copilot_eval.py `
  --cases D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\golden_cases.jsonl `
  --output-dir D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs `
  --mode offline
```

V1 only needs `offline` mode. The flag exists so an online mode can be added later without redesigning the CLI.

## 10. Testing Strategy

Tests must cover:

- JSONL case loading
- metric calculation for exact matches and list-field F1
- route accuracy calculation
- CRM write-back expectation checks
- required task matching behavior
- runner behavior on successful and failing cases

The tests should use stubbed/fake results where possible so evaluation logic remains deterministic.

## 11. Resume-Oriented Outcomes

This evaluation stack exists to unlock metrics that can be stated honestly in project writeups.

The report should expose final values for:

- structured JSON validity on the offline benchmark
- workflow success rate
- route accuracy
- required task hit rate
- average list-field F1

These numbers must come only from the local benchmark outputs and never be hand-written into the project without a matching report artifact.

## 12. Risks And Mitigations

Risk: dataset is too small to feel credible.  
Mitigation: keep scenario coverage balanced and document the exact case count in the report.

Risk: metric rules are too strict for natural-language task titles.  
Mitigation: required task matching should use controlled keyword/title matching instead of exact full-string equality.

Risk: parse metrics and workflow metrics drift away from real business value.  
Mitigation: only score fields that directly influence routing, CRM updates, and task generation.

Risk: model output variance causes noisy score comparisons.  
Mitigation: use `lead_score_range` instead of exact score equality.
