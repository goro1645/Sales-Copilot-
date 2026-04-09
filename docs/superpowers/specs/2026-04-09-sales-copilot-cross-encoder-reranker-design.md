# Sales Copilot Cross-Encoder Reranker Design

## Goal

Add a local lightweight cross-encoder reranker to the existing Sales Copilot retrieval stack so the project can support a real second-stage reranking step instead of relying only on keyword/vector hybrid scores.

## Recommended Approach

Keep the current retrieval pipeline in two explicit stages:

1. **candidate recall**
   - existing `keyword_only` and `hybrid` retrieval remain unchanged
   - `hybrid` continues to handle first-stage recall
2. **second-stage rerank**
   - run a local cross-encoder only on the recalled Top-K candidates
   - produce a final `hybrid_rerank` ordering

This is preferred over replacing `hybrid` entirely because:

- it preserves the current stable retrieval path
- it keeps latency bounded by reranking only a small candidate set
- it gives us a clear benchmark comparison: `keyword_only` vs `hybrid` vs `hybrid_rerank`

## Scope

This feature includes:

- a local reranker module
- a lightweight default cross-encoder loader with graceful fallback
- retrieval integration for second-stage reranking
- benchmark integration and tests

This feature does **not** include:

- replacing the Streamlit UI with reranker-specific controls
- reranker score caching in SQLite
- full production tuning of model choice

## Architecture

### 1. New reranker module

Create `sales_copilot/reranker.py` with:

- a small `Reranker` protocol
- a deterministic `FakeReranker` for tests
- a `CrossEncoderReranker` implementation using `sentence-transformers`
- a cached `load_default_reranker()` helper

The reranker should score `(query, chunk_text)` pairs and return one score per candidate.

### 2. Retrieval integration

Extend `sales_copilot/retrieval.py` so that:

- `hybrid` still recalls candidates first
- `reranker` can rescore the recalled rows
- output rows include:
  - `rerank_score`
  - `final_score`
  - `retrieval_mode = "hybrid_rerank"`

If the reranker cannot load, the retrieval path must fall back to the existing `hybrid` behavior.

### 3. Benchmark integration

Extend the retrieval benchmark so it reports three modes:

- `keyword_only`
- `hybrid`
- `hybrid_rerank`

Metrics stay the same:

- `Recall@1`
- `Recall@3`
- `Recall@5`
- `MRR`

The benchmark should make it easy to show whether reranking improves top-rank ordering.

## Model Choice

Use a lightweight local cross-encoder as the default reranker path. The model name should stay configurable, and load failures should be non-fatal.

The first version should optimize for:

- small footprint
- easy local execution
- benchmark comparability

not for maximum Chinese-domain accuracy.

## File Plan

### Create

- `D:\minimind\.worktrees\minimind-job-agent\sales_copilot\reranker.py`

### Modify

- `D:\minimind\.worktrees\minimind-job-agent\sales_copilot\retrieval.py`
- `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\retrieval_runner.py`
- `D:\minimind\.worktrees\minimind-job-agent\scripts\run_sales_copilot_retrieval_eval.py`
- `D:\minimind\.worktrees\minimind-job-agent\README.md`
- `D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_retrieval.py`
- `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_retrieval_runner.py`

## Testing Strategy

Tests should cover:

- local reranker scoring with `FakeReranker`
- hybrid recall followed by rerank reordering
- fallback when reranker is unavailable
- benchmark summaries including `hybrid_rerank`

Tests must not download real models. They should inject deterministic fake rerank scores.

## Success Criteria

This work is complete when:

- the repo has a local reranker abstraction
- retrieval can produce a `hybrid_rerank` mode
- benchmark reports include `hybrid_rerank`
- retrieval tests and benchmark tests pass locally
