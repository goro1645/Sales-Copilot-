# Sales Copilot Retrieval Evaluation Design

## Goal

Add a dedicated retrieval benchmark for Sales Copilot so we can measure whether `hybrid retrieval` is actually better than `keyword-only` retrieval on the local knowledge base.

This benchmark should stay narrow and explainable:
- evaluate only `product` and `playbook` knowledge chunks
- compare `keyword_only` and `hybrid` retrieval on the same query set
- report retrieval quality with standard ranking metrics

## Scope

This iteration evaluates only knowledge retrieval over `knowledge_chunks`.

Included:
- product knowledge retrieval
- sales playbook retrieval
- side-by-side comparison of `keyword_only` and `hybrid`
- retrieval-only metrics such as `Recall@K` and `MRR`

Excluded:
- account history retrieval
- end-to-end workflow quality
- CSDS parse metrics
- LLM judge or manual answer grading

## Why This Split

The project already has:
- parse quality evaluation on `CSDS`
- workflow evaluation on self-built golden cases

What is missing is a clean way to answer:

`Did hybrid retrieval improve knowledge retrieval itself?`

Mixing account history, workflow routing, and downstream prompts into the same benchmark would make that question much harder to answer honestly.

## Dataset Design

Create a small self-built retrieval benchmark file:

- `evals/sales_copilot/retrieval_cases.jsonl`

Each row should contain:

```json
{
  "case_id": "product_private_deployment",
  "query": "private deployment audit logging",
  "source_type": "product",
  "expected_chunk_ids": [1],
  "notes": "Deployment-related query should retrieve the deployment product chunk."
}
```

Required fields:
- `case_id`
- `query`
- `source_type`
- `expected_chunk_ids`

Optional fields:
- `notes`

Rules:
- `source_type` must be either `product` or `playbook`
- `expected_chunk_ids` must point to chunk ids already present in the seeded local knowledge base
- first version should stay small and high precision, around `10-20` cases total

## Evaluation Modes

Each retrieval case should be run twice:

1. `keyword_only`
   - uses the existing lexical retrieval path only

2. `hybrid`
   - uses vector similarity plus keyword blending

Both modes should return the ranked top results for the same query so we can compare them directly.

## Metrics

For each mode, compute:

- `Recall@1`
- `Recall@3`
- `Recall@5`
- `MRR`

Definitions:

- `Recall@K`
  - success if any expected chunk id appears in the top `K`

- `MRR`
  - reciprocal rank of the first expected chunk id
  - `0` if no expected chunk appears

Also include:
- `num_cases`
- `source_type_breakdown`
- per-case result rows with ranked chunk ids and scores

## Output Files

Store outputs under a new retrieval-specific output directory:

- `evals/sales_copilot/outputs_retrieval/<timestamp>/report.json`
- `evals/sales_copilot/outputs_retrieval/<timestamp>/report.md`
- `evals/sales_copilot/outputs_retrieval/<timestamp>/case_results.jsonl`

## Code Structure

Add a retrieval-specific evaluation layer instead of overloading the existing parse/workflow runner.

New files:
- `evals/sales_copilot/retrieval_cases.jsonl`
- `evals/sales_copilot/retrieval_metrics.py`
- `evals/sales_copilot/retrieval_runner.py`
- `scripts/run_sales_copilot_retrieval_eval.py`
- `tests/evals/test_retrieval_metrics.py`
- `tests/evals/test_retrieval_runner.py`

Responsibilities:

### `retrieval_metrics.py`
- compute `Recall@1`
- compute `Recall@3`
- compute `Recall@5`
- compute `MRR`
- summarize per-mode aggregates

### `retrieval_runner.py`
- load retrieval cases
- run `keyword_only` retrieval
- run `hybrid` retrieval
- collect ranked ids, scores, and mode-specific metrics

### `run_sales_copilot_retrieval_eval.py`
- CLI entrypoint
- write timestamped report artifacts

## Retrieval Interface Boundary

The benchmark should use the retrieval layer directly rather than the whole workflow graph.

This keeps the evaluation focused on:
- retrieval quality
- ranking behavior
- keyword vs hybrid comparison

Instead of:
- prompt quality
- LLM output noise
- workflow routing side effects

## Error Handling

- invalid `source_type` should fail fast
- missing expected chunk ids should fail validation before evaluation starts
- if `hybrid` retrieval falls back to keyword because the embedder is unavailable, the result should still be recorded with explicit mode metadata

## Testing Strategy

### Unit tests
- `Recall@K` calculation
- `MRR` calculation
- aggregation across multiple retrieval cases

### Integration tests
- runner loads cases and produces both `keyword_only` and `hybrid` results
- report files are written
- invalid cases fail clearly

## Expected Outcome

After this change, the project will have a dedicated retrieval benchmark that can support claims like:

- `Hybrid retrieval improves Recall@3 over keyword-only retrieval on the local knowledge benchmark`
- `Hybrid retrieval improves MRR on product/playbook retrieval cases`

This gives the RAG layer its own evidence, separate from parse metrics and workflow metrics.
