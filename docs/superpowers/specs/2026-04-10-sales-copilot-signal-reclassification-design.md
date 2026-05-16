# Sales Copilot Signal Reclassification Design

## Goal

Improve `CSDS` parse-only evaluation by adding a second-pass DeepSeek-based signal reclassification step focused on the weakest fields:

- `budget_signals`
- `timeline_signals`
- `next_steps`

The design must avoid rewriting the entire parse flow. Instead, it should preserve the current first-pass parse and insert a narrow post-processing layer that is easier to reason about, evaluate, and tune.

## Problem Statement

Current `CSDS test 800` parse-only results show the main bottlenecks are semantic boundary errors rather than JSON formatting or field-name issues.

Observed characteristics:

- `json_valid_rate = 100%`
- `customer_roles` and `confirmed_needs` are already strong
- `budget_signals` and `timeline_signals` are the weakest fields
- `next_steps` is decent but still affected by overlap with timeline-like or action-like phrases

This suggests the dominant failure mode is:

- candidate content is extracted, but placed in the wrong field
- or not emitted because the field boundary is unclear

## Recommended Approach

Use a two-stage parse architecture for the weak fields:

1. Keep the existing first-pass parse unchanged
2. Extract candidate signal phrases from the first-pass output
3. Use DeepSeek to classify each candidate into a fixed label set
4. Apply a minimal high-precision fallback only when needed
5. Rebuild the final parse result for the target fields

This is preferred over expanding keyword rules because the problem is semantic classification, not only lexical matching.

## Approaches Considered

### 1. Rule-heavy post-processing

Continue adding keyword and pattern routing rules for `budget_signals`, `timeline_signals`, and `next_steps`.

Pros:
- quick to implement
- easy to test for obvious cases

Cons:
- poor generalization
- rule explosion risk
- hard to maintain and explain

### 2. DeepSeek second-pass classification (recommended)

Preserve the current parse, then run a narrow DeepSeek classification task over extracted signal candidates.

Pros:
- better semantic boundary handling
- much more targeted than full end-to-end re-prompting
- easy to A/B test against current parse-only pipeline

Cons:
- adds one more model call per case
- requires careful output schema and confidence handling

### 3. Replace the whole parse prompt

Rewrite the first-pass prompt to directly solve the field-boundary issue in a single shot.

Pros:
- minimal pipeline complexity

Cons:
- hard to debug
- hard to know whether improvements come from extraction or classification changes
- likely to regress strong fields while chasing weak ones

## Recommended Scope

The first version only touches:

- `budget_signals`
- `timeline_signals`
- `next_steps`

It does **not** change:

- `account_name`
- `customer_roles`
- `confirmed_needs`
- `competitors`

The first version is enabled only in the `CSDS parse-only eval` path via an explicit flag. It is not initially wired into the main demo or workflow.

## Data Flow

Current flow:

`dialogue -> parse_result -> evaluation`

New evaluation flow:

`dialogue -> first-pass parse_result -> signal extraction -> DeepSeek reclassification -> lightweight fallback -> final parse_result -> evaluation`

## Intermediate Structures

### 1. Candidate extraction structure

```json
{
  "account_name": "京东客服",
  "customer_roles": ["用户", "客服"],
  "confirmed_needs": ["修改订单信息"],
  "signal_candidates": [
    {
      "candidate_id": "sig_001",
      "text": "订单完成后帮助用户完成修改",
      "speaker": "agent",
      "evidence": "用户可以留下信息，在订单完成后帮助用户完成修改",
      "normalized_text": "订单完成后帮助用户完成修改",
      "hints": ["time_like", "action_like"]
    }
  ]
}
```

### 2. Reclassification result

```json
{
  "classified_signals": [
    {
      "candidate_id": "sig_001",
      "predicted_label": "next_steps",
      "confidence": 0.62,
      "alternative_labels": ["timeline_signals"],
      "notes": "Main meaning is a follow-up action with an attached time condition."
    }
  ]
}
```

### 3. Final projected output

```json
{
  "account_name": "京东客服",
  "customer_roles": ["用户", "客服"],
  "confirmed_needs": ["修改订单信息"],
  "budget_signals": ["已下单商品不能再使用优惠券"],
  "timeline_signals": ["订单完成后"],
  "next_steps": ["留下信息", "帮助用户完成修改"],
  "competitors": []
}
```

## Candidate Extraction Strategy

Candidate extraction is intentionally narrow.

It should gather phrases from:

- first-pass `budget_signals`
- first-pass `timeline_signals`
- first-pass `next_steps`
- optional `objections` only when they contain likely budget/timeline/action semantics

This step should not re-read the full dialogue or regenerate broad summaries.

## DeepSeek Reclassification Prompt

The model task is not open-ended generation. It is a constrained classification task.

Allowed labels:

- `budget_signals`
- `timeline_signals`
- `next_steps`
- `other`

Required behavior:

- classify based on business meaning, not only keywords
- do not invent new information
- do not rewrite facts beyond minimal normalization
- return valid JSON only

### Label definitions

- `budget_signals`: price, refund, reimbursement, coupon, discount, compensation, fee restriction, cost-related constraints
- `timeline_signals`: timing commitments, deadlines, waiting periods, sequence constraints, expected processing windows
- `next_steps`: explicit actions, handling steps, support commitments, user next actions, operational follow-up
- `other`: insufficient or not relevant to the three target fields

### Output schema

```json
{
  "classified_signals": [
    {
      "candidate_id": "sig_001",
      "predicted_label": "next_steps",
      "confidence": 0.62,
      "alternative_labels": ["timeline_signals"],
      "notes": "Main meaning is a follow-up action with an attached time condition."
    }
  ]
}
```

## Lightweight Fallback Layer

This layer exists only as a high-precision safety net.

It should not become a second full rule engine.

It may do four things:

1. Fill empty fields when a highly obvious signal exists
2. Correct clearly misclassified fragments
3. Extract very stable sub-fragments such as time expressions or explicit refund/coupon phrases
4. Trigger only when a target field is empty or classification confidence is low

Examples of high-confidence fallback behavior:

- move explicit time fragments such as `一个工作日内`, `明天`, `订单完成后` into `timeline_signals`
- move explicit refund/coupon/compensation fragments into `budget_signals`
- preserve explicit action phrases such as `联系客服`, `申请退款`, `重新下单`, `留下信息` as `next_steps`

The fallback layer must not overwrite high-confidence model classifications by default.

## Integration Points

First version integration target:

- `CSDS parse-only eval` path only

Likely implementation touchpoints:

- `sales_copilot/prompts.py`
- `evals/sales_copilot/csds_runner.py`
- `evals/sales_copilot/csds_adapter.py`
- optional utility modules under `sales_copilot/` or `evals/sales_copilot/`

The main demo/workflow remains unchanged in v1.

## Configuration

Add an explicit switch for A/B evaluation:

- `use_signal_reclassification = False` by default
- enabled only in targeted eval runs

This allows side-by-side comparison of:

- baseline parse-only
- parse-only + DeepSeek reclassification

## Testing Strategy

### Unit tests

- candidate extraction from first-pass parse
- fallback behavior for high-confidence obvious cases
- final projection logic back into parse schema

### Integration tests

- mock DeepSeek classification response and verify corrected final output
- ensure strong fields remain unchanged when reclassification is enabled

### Evaluation

Run `CSDS test 800` baseline vs reclassification mode and compare:

- `average_list_field_f1`
- `budget_signals F1`
- `timeline_signals F1`
- `next_steps F1`

## Success Criteria

The first version is successful if it:

- improves `budget_signals` F1 over the current baseline
- improves `timeline_signals` F1 over the current baseline
- keeps `next_steps` stable or better
- improves overall `average_list_field_f1`
- does not reduce `json_valid_rate`

## Risks

- increased eval latency due to extra model call
- weak prompt definition can move ambiguity rather than reduce it
- overly strong fallback rules may fight the classifier instead of supporting it

## Non-Goals

This design does not aim to:

- redesign the entire main parse pipeline
- change retrieval or reranking behavior
- modify the main Sales Copilot demo UI in the first version
- solve all field-boundary problems for every field
