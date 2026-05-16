# Sales Copilot Candidate Span Generation Design

## Goal

Introduce a CSDS parse-only experiment that replaces direct second-pass field classification with:

`baseline parse -> candidate span generation -> local scoring/selection -> final projection`

The immediate goal is to improve alignment with CSDS gold span granularity for `budget_signals` and `timeline_signals` without destabilizing the existing parse-only evaluation path or the main Sales Copilot workflow.

## Problem

The current second-pass tool-call classifier is protocol-stable but semantically misaligned with CSDS gold labels:

- It classifies mostly sentence-level candidates, while CSDS gold often expects shorter span-level fragments.
- It can return semantically reasonable full clauses that still score poorly because they do not match gold granularity.
- `next_steps` is particularly sensitive to over-eager rewriting, so broad post-processing hurts overall F1.

The bottleneck is not JSON stability anymore. The bottleneck is candidate granularity.

## Scope

This design applies only to the CSDS parse-only evaluation path.

In scope:

- Add a new experimental post-parse refinement path for CSDS cases.
- Ask DeepSeek to propose multiple candidate spans copied from the original meeting note text.
- Score and select candidate spans locally.
- Limit V1 projection to `budget_signals` and `timeline_signals`; leave `next_steps` on the baseline parse result.
- Add a CLI flag so the experiment can be run on a 20-case smoke sample without touching existing default flows.

Out of scope:

- Main Sales Copilot workflow changes
- CRM/task workflow changes
- Replacing the existing signal reclassification path
- Full 800-case rollout before smoke validation succeeds

## Proposed Architecture

### 1. Candidate Generation

After the baseline parse completes, call DeepSeek with a constrained tool-call schema that returns multiple candidate spans.

The candidate generator is asked to:

- copy spans verbatim from the original `meeting_note_text`
- return multiple candidates rather than a single final field output
- assign only a coarse label:
  - `budget_signals`
  - `timeline_signals`
  - `next_steps`
  - `other`

The model must not paraphrase. Returned spans must be contiguous substrings of the source note.

### 2. Local Candidate Scoring

Candidates are scored locally rather than trusted blindly.

Scoring favors:

- shorter, purer spans over long mixed clauses
- label-consistent spans
- spans whose semantics match the target field:
  - budget-like spans for `budget_signals`
  - time-like spans for `timeline_signals`
  - action-like spans for `next_steps`

Scoring penalizes:

- spans not present in the source note
- very long multi-clause candidates
- duplicate or containment-redundant spans
- spans with conflicting mixed semantics

### 3. Field Projection

V1 only projects selected candidates into:

- `budget_signals`
- `timeline_signals`

`next_steps` remains baseline-only in this experiment. This avoids repeating the earlier problem where post-processing damaged a strong baseline field.

Projection is additive and bounded:

- at most top 2 budget candidates
- at most top 2 timeline candidates

No candidate-generation output will delete or rewrite `next_steps`.

## Data Flow

For a CSDS case:

1. Run the existing baseline parse.
2. Send `meeting_note_text` plus minimal parse context to candidate generation.
3. Receive `candidates[]` through a strict tool-call schema.
4. Filter invalid candidates:
   - empty text
   - text not found in source note
   - invalid label
5. Score candidates locally.
6. Select top candidates per field.
7. Merge into `budget_signals` and `timeline_signals`.
8. Evaluate using the existing parse-only metrics.

## Tool Schema

The candidate generation tool schema is intentionally small:

```json
{
  "name": "propose_signal_candidates",
  "parameters": {
    "type": "object",
    "properties": {
      "candidates": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "candidate_id": {"type": "string"},
            "text": {"type": "string"},
            "coarse_label": {
              "type": "string",
              "enum": ["budget_signals", "timeline_signals", "next_steps", "other"]
            }
          },
          "required": ["candidate_id", "text", "coarse_label"],
          "additionalProperties": false
        }
      }
    },
    "required": ["candidates"],
    "additionalProperties": false
  }
}
```

## Files

### New

- `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\candidate_span_refiner.py`
  - candidate tool-call request
  - validation
  - local scoring
  - projection helpers

- `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_candidate_span_refiner.py`
  - unit tests for candidate validation, scoring, and projection

### Modify

- `D:\minimind\.worktrees\minimind-job-agent\sales_copilot\prompts.py`
  - add candidate generation prompt builder

- `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\csds_runner.py`
  - add experimental refinement hook and flag threading

- `D:\minimind\.worktrees\minimind-job-agent\scripts\run_sales_copilot_eval.py`
  - add CLI flag for candidate-generation refinement

- `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_csds_runner.py`
  - cover experiment flag behavior

- `D:\minimind\.worktrees\minimind-job-agent\tests\scripts\test_run_sales_copilot_eval.py`
  - cover CLI threading of new flag

## Failure Handling

If candidate generation fails for a case:

- keep the baseline parse result unchanged
- record the candidate-generation error separately
- do not mark the main parse as failed

If the model returns candidates but they are invalid:

- drop only the invalid candidates
- continue with any valid candidates
- if no valid candidates remain, fall back to baseline

## Validation Strategy

### Phase 1

Run targeted unit tests for:

- candidate schema consumption
- span-in-source-note validation
- short-span preference over long mixed clauses
- bounded projection into budget/timeline only

### Phase 2

Run a 20-case full-CSDS smoke evaluation with the new flag enabled.

Success criteria for the smoke run:

- `json_valid_rate` remains `100%`
- no new top-level parse failures
- candidate-generation errors remain low
- at least some inspected cases show finer-grained spans than the current classifier path
- `next_steps` is not degraded by experiment logic because it remains baseline-only

## Expected Outcome

This experiment is expected to answer one question cleanly:

Can model-generated multi-candidate spans, plus local scoring, produce span granularity closer to CSDS gold than the current sentence-level second-pass classifier?

If yes, we can extend the experiment to 100 cases and then consider a full 800-case evaluation.
If no, we will know the remaining bottleneck is candidate generation quality rather than selection logic.
