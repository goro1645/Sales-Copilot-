# Sales Copilot Cross-Encoder Reranker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local lightweight cross-encoder reranker on top of the existing hybrid retrieval path and expose benchmark results for `hybrid_rerank`.

**Architecture:** Keep current `keyword_only` and `hybrid` retrieval as-is for candidate recall, then apply a second-stage reranker on recalled candidates only. Integrate the new mode into the benchmark without disturbing unrelated workflow code.

**Tech Stack:** Python, sentence-transformers, pytest, local benchmark utilities

---

## File Map

- `D:\minimind\.worktrees\minimind-job-agent\sales_copilot\reranker.py`
  - local reranker abstraction and default cross-encoder loader
- `D:\minimind\.worktrees\minimind-job-agent\sales_copilot\retrieval.py`
  - second-stage reranking integration
- `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\retrieval_runner.py`
  - benchmark support for `hybrid_rerank`
- `D:\minimind\.worktrees\minimind-job-agent\scripts\run_sales_copilot_retrieval_eval.py`
  - report includes new mode
- `D:\minimind\.worktrees\minimind-job-agent\README.md`
  - document reranker and benchmark usage
- `D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_retrieval.py`
  - retrieval rerank tests
- `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_retrieval_runner.py`
  - benchmark mode coverage

### Task 1: Add failing reranker tests

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_retrieval.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_retrieval_runner.py`

- [ ] **Step 1: Write a failing retrieval test for second-stage reranking**

```python
def test_hybrid_rerank_reorders_top_k_candidates():
    ...
```

- [ ] **Step 2: Write a failing benchmark test for the new `hybrid_rerank` mode**

```python
def test_run_retrieval_benchmark_reports_hybrid_rerank_mode():
    ...
```

- [ ] **Step 3: Run the focused tests to confirm they fail**

Run:
`& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_retrieval.py D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_retrieval_runner.py -q`

Expected: fail because reranker code and benchmark mode do not exist yet.

### Task 2: Implement local reranker abstraction

**Files:**
- Create: `D:\minimind\.worktrees\minimind-job-agent\sales_copilot\reranker.py`

- [ ] **Step 1: Add a `Reranker` protocol and `FakeReranker`**

```python
class Reranker(Protocol):
    model_name: str
    def score_pairs(self, pairs: list[tuple[str, str]]) -> list[float]:
        ...
```

- [ ] **Step 2: Add `CrossEncoderReranker` and `load_default_reranker()`**

```python
class CrossEncoderReranker:
    ...
```

- [ ] **Step 3: Run a targeted syntax check**

Run:
`& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m py_compile D:\minimind\.worktrees\minimind-job-agent\sales_copilot\reranker.py`

Expected: pass.

### Task 3: Integrate reranker into retrieval

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\sales_copilot\retrieval.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_retrieval.py`

- [ ] **Step 1: Add `hybrid_rerank_retrieve_rows(...)` and `hybrid_rerank_knowledge_chunks(...)`**

```python
def hybrid_rerank_retrieve_rows(...):
    ...
```

- [ ] **Step 2: Ensure fallback to `hybrid` when reranker is unavailable**

```python
if active_reranker is None:
    return hybrid_rows
```

- [ ] **Step 3: Run retrieval tests**

Run:
`& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_retrieval.py -q`

Expected: pass.

### Task 4: Extend retrieval benchmark with `hybrid_rerank`

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\retrieval_runner.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_retrieval_runner.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\scripts\run_sales_copilot_retrieval_eval.py`

- [ ] **Step 1: Add reranked mode to benchmark outputs**

```python
rows_by_mode = {"keyword_only": [], "hybrid": [], "hybrid_rerank": []}
```

- [ ] **Step 2: Ensure the report includes the new mode**

```python
for mode, mode_summary in summary.items():
    ...
```

- [ ] **Step 3: Run benchmark-related tests**

Run:
`& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_retrieval_runner.py D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_retrieval_metrics.py -q`

Expected: pass.

### Task 5: Document and verify

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\README.md`

- [ ] **Step 1: Document the reranker architecture and benchmark mode**

```markdown
- `hybrid_rerank`: hybrid recall followed by local cross-encoder reranking
```

- [ ] **Step 2: Run final related verification**

Run:
`& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_retrieval.py D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_retrieval_runner.py D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_retrieval_metrics.py -q`

Expected: pass.

- [ ] **Step 3: Run py_compile for touched implementation files**

Run:
`& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m py_compile D:\minimind\.worktrees\minimind-job-agent\sales_copilot\reranker.py D:\minimind\.worktrees\minimind-job-agent\sales_copilot\retrieval.py D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\retrieval_runner.py D:\minimind\.worktrees\minimind-job-agent\scripts\run_sales_copilot_retrieval_eval.py`

Expected: pass.
