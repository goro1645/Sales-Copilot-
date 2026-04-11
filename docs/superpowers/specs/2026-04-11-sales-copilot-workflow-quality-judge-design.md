# Sales Copilot Workflow Quality Judge Design

## Summary

Build a new offline `LLM judge` evaluation layer for Sales Copilot that scores the final quality of:

- CRM writeback
- task generation

using the existing workflow benchmark draft:

- `evals/sales_copilot/outputs_workflow_calibrated_30/full_csds_workflow_calibrated_30.jsonl`

The judge will not replace the existing structural workflow metrics. Instead, it will add a richer quality lens that answers questions the current metrics do not answer well, especially:

- Is the CRM writeback semantically correct and business-usable?
- Are the generated tasks actionable and structurally sound?
- Does `baseline + RAG` improve final workflow quality, not just intermediate route/stage proxies?

The first version will use an `LLM judge` with `1-5` scores, a two-stage review flow, and report both sub-scores and overall scores.

## Problem

Current workflow evaluation is too shallow for judging real output quality. It mainly checks:

- whether CRM writeback happened
- whether tasks were generated
- whether required task titles were hit

It does not directly measure:

- whether the CRM fields are appropriate
- whether the recommended next step is useful
- whether risk flags are sufficient
- whether tasks are specific, actionable, and worth executing

This makes it hard to answer the most important product question:

`Did the system produce good CRM updates and good tasks?`

## Goals

- Add a workflow-quality evaluation layer for final outputs.
- Evaluate both:
  - CRM writeback quality
  - task generation quality
- Use a judge that is closer to semantic business review than string matching.
- Preserve a clear distinction between:
  - independent business-quality judgment
  - benchmark-alignment judgment
- Support direct A/B comparisons such as:
  - baseline workflow vs baseline + RAG

## Non-Goals

- Do not replace the existing structural workflow metrics.
- Do not redesign the main workflow.
- Do not require human annotation in this phase.
- Do not turn the judge into the only source of truth for parse quality.
- Do not evaluate every internal workflow node; focus on final CRM and task outputs.

## Benchmark Input

The first version will consume:

- `evals/sales_copilot/outputs_workflow_calibrated_30/full_csds_workflow_calibrated_30.jsonl`

Each case already contains:

- source input text
- `expected_parse`
- `expected_workflow`

This dataset should be treated as an `AI-calibrated workflow benchmark draft`, not a fully human-verified workflow gold set.

## Evaluation Scope

The judge will score only final business-facing outputs:

- `actual_crm_writeback`
- `actual_generated_tasks`

It will not score:

- raw parse JSON directly
- retrieval snippets directly
- intermediate node messages
- tool-call formatting quality unless it affects final outputs

## Two-Stage Judge Flow

### Stage 1: Independent Business Review

Input:

- original case context
- actual workflow outputs only

This stage must not see the expected workflow result.

Purpose:

- judge the output on its own business merit
- avoid overfitting to benchmark wording

Questions answered:

- Is this CRM writeback correct enough to use?
- Are these tasks actionable and structurally appropriate?

### Stage 2: Benchmark Alignment Review

Input:

- the same case context
- actual workflow outputs
- `expected_workflow`
- Stage 1 scores and notes

Purpose:

- assess how well the actual output aligns with the benchmark draft
- explain whether deviations are quality problems or acceptable alternatives

This stage must not overwrite Stage 1 business-quality reasoning. It should add:

- alignment score
- delta explanation

## Judge Dimensions

### CRM Writeback

Score both:

- `field_correctness_score`
- `business_usability_score`

`field_correctness_score` should reflect whether the CRM payload is appropriate in terms of:

- opportunity stage
- account status
- risk flags
- recommended next step
- evidence quality

`business_usability_score` should reflect whether a sales or customer-facing teammate could continue working from the CRM writeback without major correction.

### Task Generation

Score both:

- `structure_correctness_score`
- `execution_quality_score`

`structure_correctness_score` should reflect whether tasks have the right structural shape:

- title
- owner
- priority
- timing or due expectation

`execution_quality_score` should reflect whether the tasks are worth executing:

- specific enough
- actionable enough
- aligned with the case
- useful for next-step progress

### Overall

Also produce:

- `overall_score`
- `verdict`
- `summary`

The first version should use three verdict bands:

- `poor`
- `acceptable`
- `good`

### Benchmark Alignment

Produce:

- `alignment_score`
- `delta_note`

This captures how closely the actual output aligns with the benchmark draft after an independent review has already happened.

## Score Scale

All quality scores will use `1-5`.

Interpretation:

- `1`: clearly poor or unsafe to use
- `2`: weak, major correction needed
- `3`: acceptable but rough
- `4`: good and mostly usable
- `5`: strong, clear, and directly useful

The same scale should be applied consistently across:

- CRM field correctness
- CRM business usability
- task structure correctness
- task execution quality
- overall score
- alignment score

## Judge Output Schema

Each case-level judge result should follow this structure:

```json
{
  "judge_result": {
    "crm_writeback": {
      "field_correctness_score": 4,
      "business_usability_score": 4,
      "strengths": ["..."],
      "issues": ["..."]
    },
    "task_generation": {
      "structure_correctness_score": 3,
      "execution_quality_score": 4,
      "strengths": ["..."],
      "issues": ["..."]
    },
    "overall": {
      "overall_score": 4,
      "verdict": "good",
      "summary": "..."
    },
    "benchmark_alignment": {
      "alignment_score": 4,
      "delta_note": "..."
    }
  }
}
```

The first version should keep this schema compact and avoid extra free-form analysis beyond:

- `strengths`
- `issues`
- `summary`
- `delta_note`

## Judge Input Packaging

### Shared Context

Each judge invocation should receive a compact, structured view of:

- `case_id`
- `meeting_note_text`
- optional customer/account context when available

### Actual Output View

The runner should normalize actual outputs before sending them to the judge:

- `actual_crm_writeback`
- `actual_generated_tasks`

`actual_generated_tasks` should be normalized into a consistent task list shape with:

- `title`
- `description`
- `priority`
- `owner`
- `timing_or_due_hint`

### Expected Output View

This should be supplied only in Stage 2:

- `expected_workflow.expected_crm_writeback`
- `expected_workflow.expected_task_bundle`

## Reporting Metrics

The report should include three layers.

### 1. Subscore Averages

- `crm_field_correctness_avg`
- `crm_business_usability_avg`
- `task_structure_correctness_avg`
- `task_execution_quality_avg`
- `overall_score_avg`
- `alignment_score_avg`

### 2. Acceptability Rates

At minimum:

- `overall_good_rate`
- `overall_acceptable_rate`
- `crm_acceptable_rate`
- `task_acceptable_rate`

Recommended thresholds:

- `good_or_better`: score `>= 4`
- `acceptable_or_better`: score `>= 3`

### 3. Variant Delta Comparison

When comparing workflow variants, the report should include deltas such as:

- `delta_overall_score_avg`
- `delta_crm_business_usability_avg`
- `delta_task_execution_quality_avg`

## First Comparison Target

The first production use of this judge should compare:

- baseline workflow
- baseline workflow + RAG

The purpose is to answer:

`Does RAG improve the final quality of CRM writeback and generated tasks?`

This is more important than only comparing route/stage proxy metrics.

## Integration Strategy

Do not modify the main workflow to support this feature.

Instead, add a new offline evaluation path:

`workflow benchmark -> run workflow variant -> collect final outputs -> run two-stage judge -> write quality report`

This should be implemented as a separate evaluation layer that consumes workflow results after execution.

## Suggested Components

### `workflow_quality_judge.py`

Responsibilities:

- build Stage 1 and Stage 2 judge messages
- call the LLM judge
- parse structured judge output

### `workflow_quality_runner.py`

Responsibilities:

- load workflow benchmark cases
- run the chosen workflow variant
- collect normalized CRM/task outputs
- invoke the judge
- write case-level result rows

### `workflow_quality_reporting.py`

Responsibilities:

- aggregate judge scores
- compute averages and acceptability rates
- compute A/B deltas
- write `report.json` and `report.md`

## Error Handling

- If workflow execution fails for a case, record the failure separately and skip judge scoring for that case.
- If Stage 1 judge fails, the case should record a judge error and not fabricate scores.
- If Stage 2 judge fails after Stage 1 succeeds, preserve Stage 1 scores and record alignment as missing.
- Reports should clearly distinguish:
  - workflow execution failures
  - Stage 1 judge failures
  - Stage 2 alignment failures

## Success Criteria

This design is successful if:

- the judge can score all 30 workflow-calibrated cases with structured outputs
- reports clearly separate CRM quality, task quality, and benchmark alignment
- the system can compare baseline vs baseline + RAG on final output quality
- the results are interpretable enough to explain why one variant is better or worse

## Risks

- judge outputs may drift toward benchmark wording rather than business judgment
- benchmark alignment may be over-weighted relative to Stage 1 independent review
- some cases may not contain enough information for confident task or CRM assessment
- LLM judge variance may make small score differences noisy

## Mitigations

- keep Stage 1 blind to expected workflow
- use a compact rubric and fixed score bands
- keep Stage 2 focused on delta explanation rather than regrading everything
- preserve case-level notes so suspicious scores can be audited
- compare variants using averaged subscores rather than over-interpreting a single case
