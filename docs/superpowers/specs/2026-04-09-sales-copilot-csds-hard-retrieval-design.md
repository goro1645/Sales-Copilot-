# CSDS-Derived Hard Retrieval Benchmark Design

## Goal
Build a medium-sized hard retrieval benchmark derived from public real CSDS customer-service phrasing to measure whether `hybrid_rerank` improves ranking quality over `hybrid` on Sales Copilot knowledge retrieval.

## Why This Benchmark Exists
The current retrieval benchmark is too easy:
- knowledge base size is very small
- keyword-only, hybrid, and hybrid_rerank all reach perfect Recall@1 / MRR
- reranker plumbing is verified, but its ranking value is not measurable

This new benchmark should create more realistic and more confusable queries without pretending to use private production search logs.

## Data Source
- Public source corpus: `CSDS`
- Query source: a mix of raw user phrasing and lightly rewritten summary/intent phrasing derived from CSDS
- Retrieval corpus: existing local `product knowledge` and `sales playbook` chunks already stored in Sales Copilot knowledge storage

This benchmark is intentionally defined as:
- `public real customer-service phrasing + manually labeled retrieval benchmark`

It is not defined as:
- real enterprise search logs
- real production CRM retrieval telemetry

## Dataset Scope
- Target size: `50-80` cases
- Primary purpose: expose ranking differences between `keyword_only`, `hybrid`, and `hybrid_rerank`
- New file:
  - `evals/sales_copilot/retrieval_cases_csds_hard.jsonl`

## Case Construction
Each case is built through three steps:
1. Select a CSDS dialogue whose user/customer wording can be mapped onto existing product/playbook knowledge.
2. Produce either:
   - a raw user phrase query, or
   - a light rewrite that preserves customer-service tone while aligning better to the Sales Copilot knowledge domain.
3. Manually label the best knowledge chunk and, when needed, acceptable alternative chunks.

## Case Types
The dataset is bucketed into three types.

### 1. product_hard
Queries that primarily ask about product capability or system behavior, but plausibly match multiple product chunks.
Examples:
- private deployment + audit logging + permissions
- CRM sync + stage updates + next-step persistence

### 2. playbook_hard
Queries that primarily ask about sales/service process handling, but plausibly match multiple playbook chunks.
Examples:
- handling objections and proposing next steps
- discovering pain points and identifying decision owners

### 3. cross_source_confusing
Queries that are legitimately confusable across product knowledge and playbook knowledge.
Examples:
- customer worries about audit controls and asks how to respond next
- customer asks about CRM integration while also needing follow-up guidance

This bucket is the most important one for demonstrating reranker value.

## Labeling Rules
- Most cases should have exactly `1` best chunk.
- A minority of cases may include `2-3` acceptable chunks when multiple answers are clearly reasonable.
- Gold labels must reflect ranking preference, not just topical overlap.
- If two chunks are both relevant but one is clearly more appropriate for the query intent, only that chunk belongs in `expected_chunk_ids`.

## Dataset Format
Each line in `retrieval_cases_csds_hard.jsonl` should follow this shape:

```json
{
  "case_id": "csds_hard_001",
  "query": "客户担心权限控制和审计日志，下一步该怎么推进",
  "query_origin": "light_rewrite",
  "case_type": "cross_source_confusing",
  "source_uid": "10473",
  "expected_chunk_ids": [2],
  "acceptable_chunk_ids": [2, 5],
  "notes": "Product chunk 2 should rank above playbook chunk 5."
}
```

## Evaluation Metrics
Primary metrics:
- `Recall@1`
- `Recall@3`
- `Recall@5`
- `MRR`

Why these metrics:
- `Recall@1` best captures reranker value
- `Recall@3` and `Recall@5` help confirm recall is preserved
- `MRR` is sensitive to rank improvements even when the correct chunk is already retrieved

## Reporting
Reports should include:
- overall metrics per retrieval mode
- per-bucket metrics for:
  - `product_hard`
  - `playbook_hard`
  - `cross_source_confusing`
- direct comparison of:
  - `keyword_only`
  - `hybrid`
  - `hybrid_rerank`

## Integration Plan
Reuse the existing retrieval evaluation stack:
- `evals/sales_copilot/retrieval_runner.py`
- `evals/sales_copilot/retrieval_metrics.py`
- `scripts/run_sales_copilot_retrieval_eval.py`

Required extensions:
1. support loading `retrieval_cases_csds_hard.jsonl`
2. preserve and report `case_type` buckets
3. compare all three retrieval modes in the same report

## Success Criteria
The benchmark is considered useful if:
- `keyword_only <= hybrid`
- `hybrid <= hybrid_rerank`
- especially on `cross_source_confusing`, `hybrid_rerank` improves `Recall@1` or `MRR`

The benchmark does not need to show improvements on every bucket to be considered successful.

## Non-Goals
This benchmark will not:
- replace CSDS parse-only evaluation
- claim access to real enterprise retrieval logs
- expand the knowledge base into a large external corpus
- evaluate full workflow quality or CRM write-back behavior
