# Full-CSDS AI-Calibrated-100 Design

## Goal

Produce a `100`-case AI-calibrated benchmark draft from the existing `full_csds_calibration_working_100.jsonl` working set by having the assistant fill a final `expected_parse` for every case.

The purpose is to quickly create a higher-quality evaluation draft that is more semantically grounded than the current weak auto-gold, while being honest that it is still AI-produced rather than fully human-calibrated.

## Problem

We already have:

- a weak `full-csds 800` benchmark adapted from CSDS summaries with local rules
- a `100`-case working set with:
  - raw context
  - weak auto-gold
  - baseline parse output
  - pre-annotation suggestions

The user now wants the assistant to directly produce the final gold draft rather than waiting on a separate human review pass. This is useful for fast iteration, but it must be represented honestly:

- it is not a fully human-calibrated benchmark
- it is an AI-generated calibration draft
- it should coexist with, not silently replace, the original working set

## Scope

This design covers:

- loading the existing `100`-case working set
- generating a final AI-reviewed `expected_parse` for each case
- preserving original context and pre-annotation history
- exporting a standalone benchmark file for immediate evaluation

In scope:

- filling `human_review.final_expected_parse` or equivalent final review fields for all `100` cases
- preserving raw source context and prior weak-gold/pre-annotation information
- exporting a final benchmark file such as `full_csds_ai_calibrated_100.jsonl`
- preserving metadata that makes the benchmark’s provenance explicit

Out of scope:

- claiming the result is fully human-calibrated
- rebuilding the `full-csds 800` weak benchmark
- changing the main Sales Copilot workflow
- building a separate annotation UI

## Provenance Rules

This output must be clearly labeled as AI-calibrated rather than human-calibrated.

Recommended naming:

- working source:
  - `full_csds_calibration_working_100.jsonl`
- final AI draft:
  - `full_csds_ai_calibrated_100.jsonl`

Recommended language in docs and outputs:

- `AI-calibrated benchmark draft`
- `AI-reviewed final_expected_parse`
- `review-ready benchmark draft`

Avoid naming that implies:

- `human_calibrated`
- `human_verified`
- `fully manual gold`

## Review Targets

The AI-calibrated pass should focus on the same four parse fields already identified as the meaningful source of benchmark drift:

- `confirmed_needs`
- `budget_signals`
- `timeline_signals`
- `next_steps`

The following fields should normally be preserved from the existing working set unless there is an obvious correction needed:

- `account_name`
- `customer_roles`
- `competitors`

## Decision Inputs

For each case, the AI-calibration pass should consider:

- `meeting_note_text`
- `user_summ`
- `agent_summ`
- `final_summ`
- `auto_expected_parse`
- `baseline_parse_result`
- `pre_annotation.corrected_expected_parse`
- `sampling_bucket`
- `pre_annotation.review_reason`

This gives the calibration pass both the raw context and the existing benchmark disagreements.

## Final Output Shape

The working file should gain an AI-authored final review block for each case.

Preferred structure:

```json
{
  "human_review": {
    "final_expected_parse": {
      "confirmed_needs": [],
      "budget_signals": [],
      "timeline_signals": [],
      "next_steps": []
    },
    "reviewed_by": "ai",
    "review_status": "completed",
    "review_note": ""
  }
}
```

Even though the field name remains `human_review` for compatibility with the existing export code, the metadata must explicitly record that this pass was AI-generated.

## Calibration Policy

The AI calibration should not blindly copy either auto-gold or baseline output.

Instead, it should:

1. interpret the raw case context
2. compare weak gold and baseline parse
3. choose the most semantically faithful field values
4. keep the output concise and field-appropriate

Field guidance:

- `confirmed_needs`
  - preserve the user’s actual problem, request, or concern
- `budget_signals`
  - include only price/refund/coupon/compensation/economic signals
- `timeline_signals`
  - include time, duration, order, processing window, or timing constraints
- `next_steps`
  - include follow-up actions, promises, or user/agent next actions

The calibration should prefer semantically clean field assignment over reproducing weak-gold overlap behavior.

## Export Behavior

After all `100` cases have AI-filled final review blocks, the exporter should generate:

- `full_csds_ai_calibrated_100.jsonl`

Each final row should contain:

- `case_id`
- `meeting_note_text`
- `customer_profile_text`
- `expected_parse`
- trace metadata such as `source_uid`, `source_split`

The exported benchmark file should consume:

- `human_review.final_expected_parse`

and should not depend on `pre_annotation` once exported.

## Files

### Reuse

- `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\calibrated_subset.py`
- `D:\minimind\.worktrees\minimind-job-agent\scripts\build_full_csds_calibrated_subset.py`
- `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_csds_calibrated_100\full_csds_calibration_working_100.jsonl`

### Likely Modify

- `D:\minimind\.worktrees\minimind-job-agent\scripts\build_full_csds_calibrated_subset.py`
  - support an AI-fill mode that writes completed review blocks

- `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\calibrated_subset.py`
  - helpers for writing AI review metadata and final benchmark export

- `D:\minimind\.worktrees\minimind-job-agent\README.md`
  - document the difference between weak gold, AI-calibrated draft, and future human-calibrated benchmark

## Success Criteria

This work is successful if:

- we can fill final review outputs for all `100` working-set cases
- the output provenance clearly records that the benchmark is AI-calibrated, not human-calibrated
- the final exported benchmark can be evaluated by the existing parse-only evaluation pipeline
- the original working file remains available as the traceable source artifact

## Expected Outcome

After this work, the project should have three distinct benchmark tiers:

1. `full-csds 800`
   - large weak benchmark
   - trend tracking only

2. `full_csds_calibration_working_100`
   - traceable review workspace
   - contains weak gold, baseline parse, and pre-annotation

3. `full_csds_ai_calibrated_100`
   - AI-generated high-quality draft benchmark
   - useful for faster iteration before any later human verification

This gives us a practical near-term benchmark upgrade without pretending we already have a fully human-reviewed dataset.
