# Sales Copilot Semantic Metrics Design

## Goal

Add a semantic parse-evaluation layer that is closer to "semantic correctness is enough" while preserving the existing exact/loose string-based parse metrics for regression tracking.

The new semantic metrics should be usable on the `AI-calibrated 100` benchmark draft first, and later on other parse-only datasets if we decide that the signal is helpful.

## Problem

The current parse metrics in `evals/sales_copilot/metrics.py` are anchored to list-item string matching:

- item containment
- light phrase normalization
- exact field placement

This works well for stable regression checks, but it over-penalizes outputs that are semantically correct while differing in:

- wording
- phrase granularity
- sentence compression
- action-vs-time phrasing

This is especially visible for:

- `budget_signals`
- `timeline_signals`
- `next_steps`

After creating the `AI-calibrated 100` benchmark draft, we now have a better evaluation target than weak auto-gold, but we still need a metric that is less brittle than current string-matching recall/F1.

## Scope

In scope:

- add semantic list-field metrics alongside the current metrics
- compute semantic precision / recall / f1 for the list fields
- preserve the existing metrics unchanged
- expose the semantic metrics in evaluation summaries and reports
- use a multilingual embedding model for semantic matching
- add field-specific semantic guards so nearby meanings do not get credit in the wrong field

Out of scope:

- replacing the current list-field metrics
- adding LLM-as-judge to the primary evaluation loop
- changing the parse prompts or workflow behavior
- creating a human review UI

## Recommended Approach

Use a hybrid semantic metric:

1. embed each predicted/gold list item
2. compute pairwise semantic similarity
3. apply field-specific semantic guards
4. run one-to-one matching
5. derive semantic precision / recall / f1

This keeps the evaluation:

- fully automatic
- batchable
- reproducible
- more tolerant of valid paraphrases

LLM judge remains a future calibration tool for disputed cases, not the primary metric.

## Metric Definition

The new metrics apply to the list fields:

- `customer_roles`
- `confirmed_needs`
- `budget_signals`
- `timeline_signals`
- `next_steps`
- `competitors`

### Existing Metrics

Keep the existing outputs unchanged:

- `list_field_precision`
- `list_field_recall`
- `list_field_f1`
- `average_list_field_f1`

### New Metrics

Add:

- `semantic_list_field_precision`
- `semantic_list_field_recall`
- `semantic_list_field_f1`
- `average_semantic_list_field_f1`

At the per-case level, each parse metrics payload should also expose:

- `semantic_list_field_precision[field]`
- `semantic_list_field_recall[field]`
- `semantic_list_field_f1[field]`
- `semantic_list_field_applicable[field]`

## Matching Strategy

### Item Normalization

Before embedding:

- strip whitespace
- lowercase
- collapse trivial punctuation noise

Do not aggressively rewrite meaning-bearing content.

### Embedding Model

Reuse the multilingual sentence-transformer path already used in retrieval:

- default model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`

This keeps:

- Chinese coverage
- local cache reuse
- no new model family to manage

The semantic metrics module should load the embedder lazily and cache it.

### Pairwise Similarity

For each field:

- compute cosine similarity for all `(gold_item, predicted_item)` pairs
- discard any pair that fails the field guard
- match remaining pairs one-to-one

The matching should prefer the best global set of matches rather than letting one predicted item satisfy multiple gold items.

Because field lists are small, a simple maximum-weight matching approach is acceptable.

### Thresholds

Start with explicit, field-specific thresholds:

- `customer_roles`: `0.84`
- `confirmed_needs`: `0.80`
- `budget_signals`: `0.78`
- `timeline_signals`: `0.78`
- `next_steps`: `0.78`
- `competitors`: `0.82`

These are initial defaults, not permanently fixed research values.

The implementation should keep them in a single configuration table for easy future tuning.

## Field Guards

Similarity alone is not enough. A pair should only be eligible if it also satisfies a field-specific semantic guard.

### Budget Signals

The pair is eligible only if both sides contain at least one budget/economic cue such as:

- refund
- compensation
- coupon
- discount
- price
- fee
- 差价
- 优惠券
- 退款
- 补偿
- 价格
- 价保

### Timeline Signals

The pair is eligible only if both sides contain a time/order cue such as:

- today
- tomorrow
- after
- within
- business day
- 今天
- 明天
- 之后
- 完成后
- 工作日内
- 稍后
- 尽快

### Next Steps

The pair is eligible only if both sides contain an action/follow-up cue such as:

- contact
- submit
- apply
- modify
- reorder
- return
- 联系
- 提交
- 申请
- 修改
- 重新下单
- 寄回
- 回复
- 处理

### Other Fields

- `confirmed_needs`
- `customer_roles`
- `competitors`

can use a lighter or empty guard initially, because their main problem is phrasing rather than field-boundary confusion.

## Empty/Invalid Cases

Semantic metrics should mirror the current parse-metric applicability behavior:

- if both gold and prediction are empty for a field: not applicable
- if one side is empty and the other is not: applicable, score `0`
- if parse JSON is invalid: semantic metrics should also zero out on applicable fields

This keeps semantic and legacy metrics comparable.

## Reporting

Update report generation so `report.json` and `report.md` include:

- `semantic_list_field_precision`
- `semantic_list_field_recall`
- `semantic_list_field_f1`
- `average_semantic_list_field_f1`

The markdown report should keep the current parse table and append the semantic metrics in the same section.

This avoids breaking downstream consumers that already expect the existing metrics.

## Files

### Reuse

- `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\metrics.py`
- `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\reporting.py`
- `D:\minimind\.worktrees\minimind-job-agent\sales_copilot\retrieval.py`
- `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_sales_copilot_metrics.py`

### Likely Modify

- `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\metrics.py`
  - add semantic metric helpers and summary aggregation

- `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\reporting.py`
  - include the semantic summary values in markdown and JSON reports

- `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_sales_copilot_metrics.py`
  - add semantic matching and aggregation tests

## Success Criteria

This work is successful if:

- semantic metrics are computed without breaking the existing parse metrics
- semantically equivalent paraphrases score as matches when field guards agree
- cross-field near-matches do not receive credit
- the semantic summary appears in the normal report output
- the new metrics can be run on `full_csds_ai_calibrated_100.jsonl`

## Expected Outcome

After this work, parse-only evaluation will have two complementary views:

1. legacy string-anchored metrics
   - good for regression tracking
   - stable and conservative

2. semantic list-field metrics
   - better aligned with "semantic correctness is enough"
   - especially useful on the `AI-calibrated 100` benchmark draft

This gives us a more honest way to evaluate improvements that change phrasing without changing meaning.
