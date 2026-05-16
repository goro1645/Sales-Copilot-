# Full-CSDS Gold Audit Design

## Goal

Audit the quality of the auto-generated `expected_parse` labels used by the `full-csds` parse-only benchmark, so we can determine whether the 800-case evaluation is a trustworthy weak benchmark or whether specific fields are too noisy to guide model decisions.

## Problem

The current `full-csds` benchmark does not use a fully human-verified gold set. Instead, it adapts official CSDS fields (`UserSumm`, `AgentSumm`, `FinalSumm`) into `expected_parse` using local rules. This makes large-scale evaluation possible, but it also creates a risk:

- field boundaries may be noisy
- `timeline_signals` and `budget_signals` may absorb full customer-service sentences rather than pure signals
- `timeline_signals` / `budget_signals` may overlap heavily with `next_steps`
- benchmark scores may over-penalize semantically correct outputs if auto-gold granularity is inconsistent

Before changing model behavior or evaluation metrics further, we need evidence about the quality of this auto-gold.

## Scope

This design applies only to auditing the `full-csds` auto-generated gold used in offline parse-only evaluation.

In scope:

- build a stratified `50`-case audit sample from `full-csds` `test`
- preserve raw source context (`UserSumm`, `AgentSumm`, `FinalSumm`)
- preserve generated `expected_parse`
- assign each sampled case to an audit bucket
- compute structural warning signals such as field overlap
- generate an audit-ready JSONL file and a machine-readable summary

Out of scope:

- changing the main parse model
- changing the main Sales Copilot workflow
- changing the existing 800-case benchmark scoring
- final human labeling UI

## Sampling Strategy

The audit sample should be stratified rather than purely random. Target size is `50` cases with these buckets:

1. `ordinary`: `15`
   - `budget_signals` empty
   - `timeline_signals` empty
   - `next_steps` non-empty

2. `timeline_nonempty`: `15`
   - `timeline_signals` non-empty

3. `budget_nonempty`: `10`
   - `budget_signals` non-empty

4. `field_overlap_high_risk`: `10`
   - `timeline_signals ∩ next_steps` non-empty
   - or `budget_signals ∩ next_steps` non-empty

Sampling should be deterministic so results can be reproduced.

## Audit Record Structure

Each sampled row should contain:

- `case_id`
- `source_uid`
- `source_split`
- `audit_bucket`
- `meeting_note_text`
- `user_summ`
- `agent_summ`
- `final_summ`
- `expected_parse`
- `heuristic_flags`
- `audit_label`
- `audit_note`

`audit_label` and `audit_note` are left blank for human review in V1.

`heuristic_flags` should include high-signal warnings such as:

- `timeline_next_overlap`
- `budget_next_overlap`
- `timeline_contains_non_time_like_sentence`
- `budget_contains_non_budget_like_sentence`
- `next_steps_contains_budget_sentence`

These flags are not final judgments. They are review hints.

## Outputs

V1 should produce two artifacts:

1. `full_csds_gold_audit_sample.jsonl`
   - audit-ready sample rows

2. `full_csds_gold_audit_summary.json`
   - bucket counts
   - overlap counts
   - heuristic warning counts

The summary is intended to answer:

- how much obvious overlap exists in the sampled gold
- whether `timeline_signals` and `budget_signals` look structurally suspicious
- whether the full benchmark should be treated as weak gold

## Files

### New

- `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\gold_audit.py`
  - audit bucketing
  - deterministic stratified sampling
  - heuristic flag generation
  - sample/summary helpers

- `D:\minimind\.worktrees\minimind-job-agent\scripts\build_full_csds_gold_audit.py`
  - command-line entrypoint for generating audit artifacts

- `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_gold_audit.py`
  - unit tests for bucket assignment, sampling, and summary generation

### Modify

- `D:\minimind\.worktrees\minimind-job-agent\README.md`
  - add audit command and explain that full-CSDS is an adapted weak benchmark

## Success Criteria

This work is successful if:

- we can reproducibly generate a `50`-case stratified audit sample from `full-csds test`
- each row contains both raw source summaries and generated `expected_parse`
- the summary quantifies overlap and warning patterns without requiring manual editing first
- we have enough evidence to decide whether the `full-csds 800` benchmark should be described as weak gold

## Expected Outcome

This audit will not directly improve model scores. Its value is diagnostic.

After running it, we should be able to say one of:

- the auto-gold is structurally acceptable as a weak benchmark
- or specific fields such as `timeline_signals` / `budget_signals` are noisy enough that benchmark scores must be interpreted with caution
