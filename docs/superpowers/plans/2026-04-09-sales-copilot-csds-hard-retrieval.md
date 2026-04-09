# CSDS Hard Retrieval Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a CSDS-derived hard retrieval benchmark that buckets difficult cases and shows whether `hybrid_rerank` improves retrieval quality over `hybrid`.

**Architecture:** Reuse the existing retrieval benchmark pipeline and extend it with a new JSONL dataset, richer case metadata, bucket-aware metrics, and report rendering. Keep the retrieval corpus unchanged; only add a harder query set derived from public CSDS phrasing so the benchmark stays honest and easy to reproduce.

**Tech Stack:** Python, JSONL datasets, pytest, existing Sales Copilot retrieval benchmark tooling

---

## File Map

- Create: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\retrieval_cases_csds_hard.jsonl`
  - New hard retrieval dataset derived from CSDS phrasing.
- Modify: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\retrieval_runner.py`
  - Load richer case metadata and compute bucket-aware metrics.
- Modify: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\retrieval_metrics.py`
  - Add helper(s) to summarize retrieval metrics by case bucket.
- Modify: `D:\minimind\.worktrees\minimind-job-agent\scripts\run_sales_copilot_retrieval_eval.py`
  - Render overall and per-bucket results in reports.
- Modify: `D:\minimind\.worktrees\minimind-job-agent\README.md`
  - Document the new benchmark and how to run it.
- Test: `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_retrieval_runner.py`
  - Add loader and benchmark assertions for the new hard dataset metadata.
- Test: `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_retrieval_metrics.py`
  - Add per-bucket summary assertions.

### Task 1: Add Failing Tests For Hard Retrieval Metadata

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_retrieval_runner.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_retrieval_metrics.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_load_retrieval_cases_reads_csds_hard_dataset_metadata():
    path = Path(__file__).resolve().parents[2] / "evals" / "sales_copilot" / "retrieval_cases_csds_hard.jsonl"

    cases = load_retrieval_cases(path)

    assert len(cases) >= 50
    assert {"product_hard", "playbook_hard", "cross_source_confusing"} <= {
        case["case_type"] for case in cases
    }
    assert any(case["query_origin"] == "raw_user_phrase" for case in cases)
    assert any(case["query_origin"] == "light_rewrite" for case in cases)


def test_run_retrieval_benchmark_includes_bucket_summary():
    results = run_retrieval_benchmark(cases_path=cases_path, db_path=db_path, embedder=embedder, reranker=reranker)

    assert "bucket_summary" in results
    assert "cross_source_confusing" in results["bucket_summary"]["hybrid_rerank"]


def test_summarize_retrieval_metrics_by_bucket_separates_case_types():
    summary = summarize_retrieval_metrics_by_bucket(
        {
            "hybrid": [
                {"case_type": "product_hard", "recall_at_1": 1.0, "recall_at_3": 1.0, "recall_at_5": 1.0, "mrr": 1.0},
                {"case_type": "cross_source_confusing", "recall_at_1": 0.0, "recall_at_3": 1.0, "recall_at_5": 1.0, "mrr": 0.5},
            ]
        }
    )

    assert summary["hybrid"]["product_hard"]["recall_at_1"] == 1.0
    assert summary["hybrid"]["cross_source_confusing"]["mrr"] == 0.5
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```powershell
& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest `
  D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_retrieval_runner.py `
  D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_retrieval_metrics.py -q
```

Expected: FAIL because hard dataset fields (`case_type`, `query_origin`, bucket summaries) do not exist yet.

- [ ] **Step 3: Implement the minimal code to make the tests pass**

Touch:
- `retrieval_runner.py`
- `retrieval_metrics.py`

Add:
- richer `RetrievalCase` metadata
- `acceptable_chunk_ids` support
- bucket summary helper

- [ ] **Step 4: Run tests to verify they pass**

Run the same pytest command again.

Expected: PASS for the newly added tests.

- [ ] **Step 5: Commit**

```bash
git add tests/evals/test_retrieval_runner.py tests/evals/test_retrieval_metrics.py evals/sales_copilot/retrieval_runner.py evals/sales_copilot/retrieval_metrics.py
git commit -m "feat: add bucketed hard retrieval benchmark metadata"
```

### Task 2: Add The CSDS-Derived Hard Retrieval Dataset

**Files:**
- Create: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\retrieval_cases_csds_hard.jsonl`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_retrieval_runner.py`

- [ ] **Step 1: Write the failing dataset assertions**

```python
def test_load_retrieval_cases_reads_repository_hard_dataset_and_preserves_case_mix():
    path = Path(__file__).resolve().parents[2] / "evals" / "sales_copilot" / "retrieval_cases_csds_hard.jsonl"

    cases = load_retrieval_cases(path)

    assert len(cases) >= 50
    assert sum(case["case_type"] == "product_hard" for case in cases) >= 10
    assert sum(case["case_type"] == "playbook_hard" for case in cases) >= 10
    assert sum(case["case_type"] == "cross_source_confusing" for case in cases) >= 10
```

- [ ] **Step 2: Run the targeted test to verify it fails**

Run:
```powershell
& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest `
  D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_retrieval_runner.py::test_load_retrieval_cases_reads_repository_hard_dataset_and_preserves_case_mix -q
```

Expected: FAIL because the hard dataset file does not exist yet.

- [ ] **Step 3: Create the hard dataset**

Create `retrieval_cases_csds_hard.jsonl` with:
- `50-80` cases
- `raw_user_phrase` and `light_rewrite` query origins
- `product_hard`, `playbook_hard`, `cross_source_confusing` case types
- mostly single-answer gold labels with some `acceptable_chunk_ids`

- [ ] **Step 4: Run the targeted test to verify it passes**

Run the same pytest command again.

Expected: PASS with the new dataset file in place.

- [ ] **Step 5: Commit**

```bash
git add evals/sales_copilot/retrieval_cases_csds_hard.jsonl tests/evals/test_retrieval_runner.py
git commit -m "data: add csds-derived hard retrieval benchmark cases"
```

### Task 3: Wire Reports And CLI To Show Bucket Results

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\scripts\run_sales_copilot_retrieval_eval.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_retrieval_runner.py`

- [ ] **Step 1: Write the failing report test**

```python
def test_write_retrieval_report_renders_bucket_summary(tmp_path: Path):
    output_dir = tmp_path / "outputs"
    payload = {
        "summary": {"hybrid_rerank": {"recall_at_1": 0.9}},
        "bucket_summary": {
            "hybrid_rerank": {
                "cross_source_confusing": {"recall_at_1": 0.8, "mrr": 0.85}
            }
        },
        "case_results": [],
    }

    paths = write_retrieval_report(output_dir=output_dir, payload=payload)
    report_md = paths["report_md"].read_text(encoding="utf-8")

    assert "Bucket Summary" in report_md
    assert "cross_source_confusing" in report_md
```

- [ ] **Step 2: Run the targeted test to verify it fails**

Run:
```powershell
& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest `
  D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_retrieval_runner.py::test_write_retrieval_report_renders_bucket_summary -q
```

Expected: FAIL because the markdown report does not render bucket sections yet.

- [ ] **Step 3: Implement report rendering changes**

Update `run_sales_copilot_retrieval_eval.py` so the markdown report includes:
- overall mode table
- per-bucket mode table
- optional case count hints

- [ ] **Step 4: Run the targeted test to verify it passes**

Run the same pytest command again.

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/run_sales_copilot_retrieval_eval.py tests/evals/test_retrieval_runner.py
git commit -m "feat: render bucketed retrieval benchmark reports"
```

### Task 4: Run Verification And Benchmark The Hard Set

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\README.md`

- [ ] **Step 1: Document the new benchmark**

Add a README section that explains:
- the benchmark uses CSDS-derived hard queries
- it compares `keyword_only`, `hybrid`, and `hybrid_rerank`
- it reports overall and per-bucket metrics

- [ ] **Step 2: Run all targeted tests**

Run:
```powershell
& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest `
  D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_retrieval_runner.py `
  D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_retrieval_metrics.py `
  D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_retrieval.py -q
```

Expected: PASS.

- [ ] **Step 3: Run the hard retrieval benchmark**

Run:
```powershell
& 'D:\anaconda\envs\minimind_job_agent\python.exe' `
  D:\minimind\.worktrees\minimind-job-agent\scripts\run_sales_copilot_retrieval_eval.py `
  --cases D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\retrieval_cases_csds_hard.jsonl `
  --db-path D:\minimind\.worktrees\minimind-job-agent\data\sales_copilot\sales_copilot.db `
  --output-dir D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_retrieval_hard
```

Expected:
- timestamped report directory is created
- `report.json` and `report.md` include overall and bucket summaries
- hard-set metrics show whether `hybrid_rerank` improves `Recall@1` or `MRR` on `cross_source_confusing`

- [ ] **Step 4: Review the benchmark result and summarize the outcome**

Check:
- whether `hybrid_rerank` beats or ties `hybrid` overall
- whether `cross_source_confusing` shows the clearest improvement
- whether any bucket needs more cases

- [ ] **Step 5: Commit**

```bash
git add README.md scripts/run_sales_copilot_retrieval_eval.py evals/sales_copilot/retrieval_cases_csds_hard.jsonl evals/sales_copilot/retrieval_runner.py evals/sales_copilot/retrieval_metrics.py tests/evals/test_retrieval_runner.py tests/evals/test_retrieval_metrics.py
git commit -m "feat: add csds hard retrieval benchmark"
```
