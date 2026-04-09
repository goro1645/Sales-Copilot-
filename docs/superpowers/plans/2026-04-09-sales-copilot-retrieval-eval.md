# Sales Copilot Retrieval Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated retrieval benchmark that compares `keyword_only` and `hybrid` retrieval over the local product/playbook knowledge base.

**Architecture:** Keep this benchmark separate from the existing parse/workflow evaluation stack. Add a small retrieval-case dataset, a retrieval metrics module, a focused runner that calls the retrieval layer directly, and a CLI that writes timestamped reports.

**Tech Stack:** Python, JSONL, pytest, SQLite

---

## File Map

- Create: `evals/sales_copilot/retrieval_cases.jsonl`
  - Small gold query set with expected chunk ids.
- Create: `evals/sales_copilot/retrieval_metrics.py`
  - `Recall@1`, `Recall@3`, `Recall@5`, `MRR`, and per-mode summarization.
- Create: `evals/sales_copilot/retrieval_runner.py`
  - Loads cases, executes retrieval in `keyword_only` and `hybrid` modes, and writes case-level results.
- Create: `scripts/run_sales_copilot_retrieval_eval.py`
  - CLI wrapper for running the benchmark and saving reports.
- Create: `tests/evals/test_retrieval_metrics.py`
  - Metric unit tests.
- Create: `tests/evals/test_retrieval_runner.py`
  - Runner integration tests.
- Modify: `evals/sales_copilot/reporting.py`
  - Optional helper reuse for timestamped report writing if it reduces duplication cleanly.
- Modify: `README.md`
  - Document retrieval benchmark purpose, command, and metric meanings.

### Task 1: Add a retrieval benchmark dataset

**Files:**
- Create: `D:/minimind/.worktrees/minimind-job-agent/evals/sales_copilot/retrieval_cases.jsonl`
- Test: `D:/minimind/.worktrees/minimind-job-agent/tests/evals/test_retrieval_runner.py`

- [ ] **Step 1: Write the failing dataset validation test**

```python
from evals.sales_copilot.retrieval_runner import load_retrieval_cases


def test_load_retrieval_cases_reads_expected_fields():
    cases = load_retrieval_cases(
        "D:/minimind/.worktrees/minimind-job-agent/evals/sales_copilot/retrieval_cases.jsonl"
    )

    assert cases
    assert {"case_id", "query", "source_type", "expected_chunk_ids"} <= set(cases[0].keys())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest D:/minimind/.worktrees/minimind-job-agent/tests/evals/test_retrieval_runner.py::test_load_retrieval_cases_reads_expected_fields -v`
Expected: FAIL because the dataset file or loader does not exist yet.

- [ ] **Step 3: Create the initial retrieval dataset**

Create `retrieval_cases.jsonl` with around `10-12` precise cases, evenly split between `product` and `playbook`.

Seed examples:

```json
{"case_id":"product_private_deployment","query":"private deployment audit logging","source_type":"product","expected_chunk_ids":[1],"notes":"Deployment-related query should rank the deployment product chunk first."}
{"case_id":"product_crm_integration","query":"crm integration api sync","source_type":"product","expected_chunk_ids":[2],"notes":"CRM integration query should retrieve the integration product chunk."}
{"case_id":"playbook_discovery_questions","query":"discovery questions for qualification","source_type":"playbook","expected_chunk_ids":[4],"notes":"Qualification wording should map to discovery playbook guidance."}
{"case_id":"playbook_security_objection","query":"security objection private deployment checklist","source_type":"playbook","expected_chunk_ids":[5],"notes":"Security objection query should retrieve objection-handling guidance."}
```

Make the final ids match the actual seeded knowledge chunk order already used by `sample_product_chunks()` and `sample_playbook_chunks()`.

- [ ] **Step 4: Add the loader implementation**

In `evals/sales_copilot/retrieval_runner.py`, add:

```python
import json
from pathlib import Path


def load_retrieval_cases(path: str | Path) -> list[dict]:
    rows: list[dict] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            rows.append(json.loads(text))
    return rows
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest D:/minimind/.worktrees/minimind-job-agent/tests/evals/test_retrieval_runner.py::test_load_retrieval_cases_reads_expected_fields -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git -C D:/minimind/.worktrees/minimind-job-agent add evals/sales_copilot/retrieval_cases.jsonl evals/sales_copilot/retrieval_runner.py tests/evals/test_retrieval_runner.py
git -C D:/minimind/.worktrees/minimind-job-agent commit -m "data: add retrieval benchmark cases"
```

### Task 2: Add retrieval metrics

**Files:**
- Create: `D:/minimind/.worktrees/minimind-job-agent/evals/sales_copilot/retrieval_metrics.py`
- Test: `D:/minimind/.worktrees/minimind-job-agent/tests/evals/test_retrieval_metrics.py`

- [ ] **Step 1: Write the failing metric tests**

```python
from evals.sales_copilot.retrieval_metrics import reciprocal_rank, recall_at_k, summarize_retrieval_metrics


def test_recall_at_k_returns_one_when_expected_id_is_in_top_k():
    assert recall_at_k(expected_ids=[5], ranked_ids=[7, 5, 9], k=3) == 1.0
    assert recall_at_k(expected_ids=[5], ranked_ids=[7, 5, 9], k=1) == 0.0


def test_reciprocal_rank_uses_first_matching_rank():
    assert reciprocal_rank(expected_ids=[5], ranked_ids=[7, 5, 9]) == 0.5
    assert reciprocal_rank(expected_ids=[5], ranked_ids=[7, 9]) == 0.0


def test_summarize_retrieval_metrics_averages_scores():
    summary = summarize_retrieval_metrics(
        {
            "keyword_only": [
                {"recall_at_1": 1.0, "recall_at_3": 1.0, "recall_at_5": 1.0, "mrr": 1.0},
                {"recall_at_1": 0.0, "recall_at_3": 1.0, "recall_at_5": 1.0, "mrr": 0.5},
            ]
        }
    )

    assert summary["keyword_only"]["recall_at_1"] == 0.5
    assert summary["keyword_only"]["recall_at_3"] == 1.0
    assert summary["keyword_only"]["mrr"] == 0.75
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest D:/minimind/.worktrees/minimind-job-agent/tests/evals/test_retrieval_metrics.py -v`
Expected: FAIL because `retrieval_metrics.py` does not exist yet.

- [ ] **Step 3: Implement the metrics module**

Create `retrieval_metrics.py`:

```python
from __future__ import annotations


def recall_at_k(*, expected_ids: list[int], ranked_ids: list[int], k: int) -> float:
    return 1.0 if set(expected_ids) & set(ranked_ids[:k]) else 0.0


def reciprocal_rank(*, expected_ids: list[int], ranked_ids: list[int]) -> float:
    expected = set(expected_ids)
    for index, chunk_id in enumerate(ranked_ids, start=1):
        if chunk_id in expected:
            return 1.0 / index
    return 0.0


def summarize_retrieval_metrics(rows_by_mode: dict[str, list[dict]]) -> dict[str, dict]:
    summary: dict[str, dict] = {}
    for mode, rows in rows_by_mode.items():
        total = len(rows) or 1
        summary[mode] = {
            "num_cases": len(rows),
            "recall_at_1": sum(row["recall_at_1"] for row in rows) / total,
            "recall_at_3": sum(row["recall_at_3"] for row in rows) / total,
            "recall_at_5": sum(row["recall_at_5"] for row in rows) / total,
            "mrr": sum(row["mrr"] for row in rows) / total,
        }
    return summary
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest D:/minimind/.worktrees/minimind-job-agent/tests/evals/test_retrieval_metrics.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C D:/minimind/.worktrees/minimind-job-agent add evals/sales_copilot/retrieval_metrics.py tests/evals/test_retrieval_metrics.py
git -C D:/minimind/.worktrees/minimind-job-agent commit -m "feat: add retrieval evaluation metrics"
```

### Task 3: Add retrieval runner

**Files:**
- Modify: `D:/minimind/.worktrees/minimind-job-agent/evals/sales_copilot/retrieval_runner.py`
- Test: `D:/minimind/.worktrees/minimind-job-agent/tests/evals/test_retrieval_runner.py`

- [ ] **Step 1: Write the failing runner test**

```python
from pathlib import Path

from evals.sales_copilot.retrieval_runner import run_retrieval_benchmark
from sales_copilot.tools import sample_playbook_chunks, sample_product_chunks, seed_knowledge_chunks


def test_run_retrieval_benchmark_returns_keyword_and_hybrid_results(tmp_path: Path):
    db_path = tmp_path / "sales.db"
    seed_knowledge_chunks(db_path, sample_product_chunks() + sample_playbook_chunks())

    results = run_retrieval_benchmark(
        cases_path="D:/minimind/.worktrees/minimind-job-agent/evals/sales_copilot/retrieval_cases.jsonl",
        db_path=db_path,
    )

    assert "keyword_only" in results["summary"]
    assert "hybrid" in results["summary"]
    assert results["case_results"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest D:/minimind/.worktrees/minimind-job-agent/tests/evals/test_retrieval_runner.py::test_run_retrieval_benchmark_returns_keyword_and_hybrid_results -v`
Expected: FAIL because the runner does not exist yet.

- [ ] **Step 3: Implement the runner**

Extend `retrieval_runner.py`:

```python
from __future__ import annotations

from collections import defaultdict

from evals.sales_copilot.retrieval_metrics import recall_at_k, reciprocal_rank, summarize_retrieval_metrics
from sales_copilot.retrieval import hybrid_retrieve_knowledge_chunks
from sales_copilot.tools import keyword_retrieve
from sales_copilot import storage


def _keyword_only_retrieve(db_path, *, source_type: str, query: str, top_k: int = 5) -> list[dict]:
    rows = storage.list_knowledge_chunks(db_path, source_type=source_type)
    return keyword_retrieve(query, rows, top_k=top_k)


def run_retrieval_benchmark(*, cases_path, db_path, top_k: int = 5) -> dict:
    cases = load_retrieval_cases(cases_path)
    rows_by_mode = defaultdict(list)
    case_results = []

    for case in cases:
        per_mode = {}
        for mode in ("keyword_only", "hybrid"):
            if mode == "keyword_only":
                ranked = _keyword_only_retrieve(db_path, source_type=case["source_type"], query=case["query"], top_k=top_k)
            else:
                ranked = hybrid_retrieve_knowledge_chunks(db_path, source_type=case["source_type"], query=case["query"], top_k=top_k)

            ranked_ids = [int(row["id"]) for row in ranked]
            metrics = {
                "recall_at_1": recall_at_k(expected_ids=case["expected_chunk_ids"], ranked_ids=ranked_ids, k=1),
                "recall_at_3": recall_at_k(expected_ids=case["expected_chunk_ids"], ranked_ids=ranked_ids, k=3),
                "recall_at_5": recall_at_k(expected_ids=case["expected_chunk_ids"], ranked_ids=ranked_ids, k=5),
                "mrr": reciprocal_rank(expected_ids=case["expected_chunk_ids"], ranked_ids=ranked_ids),
            }
            rows_by_mode[mode].append(metrics)
            per_mode[mode] = {
                "ranked_ids": ranked_ids,
                "metrics": metrics,
            }

        case_results.append(
            {
                "case_id": case["case_id"],
                "query": case["query"],
                "source_type": case["source_type"],
                "expected_chunk_ids": case["expected_chunk_ids"],
                "results": per_mode,
            }
        )

    return {
        "summary": summarize_retrieval_metrics(dict(rows_by_mode)),
        "case_results": case_results,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest D:/minimind/.worktrees/minimind-job-agent/tests/evals/test_retrieval_runner.py::test_run_retrieval_benchmark_returns_keyword_and_hybrid_results -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C D:/minimind/.worktrees/minimind-job-agent add evals/sales_copilot/retrieval_runner.py tests/evals/test_retrieval_runner.py
git -C D:/minimind/.worktrees/minimind-job-agent commit -m "feat: add retrieval benchmark runner"
```

### Task 4: Add a CLI entrypoint and report files

**Files:**
- Create: `D:/minimind/.worktrees/minimind-job-agent/scripts/run_sales_copilot_retrieval_eval.py`
- Test: `D:/minimind/.worktrees/minimind-job-agent/tests/evals/test_retrieval_runner.py`

- [ ] **Step 1: Write the failing CLI/report test**

```python
from pathlib import Path

from scripts.run_sales_copilot_retrieval_eval import write_retrieval_report


def test_write_retrieval_report_creates_report_files(tmp_path: Path):
    output_dir = tmp_path / "outputs"
    payload = {
        "summary": {"keyword_only": {"num_cases": 1}, "hybrid": {"num_cases": 1}},
        "case_results": [{"case_id": "case-1"}],
    }

    paths = write_retrieval_report(output_dir=output_dir, payload=payload)

    assert paths["report_json"].exists()
    assert paths["report_md"].exists()
    assert paths["case_results_jsonl"].exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest D:/minimind/.worktrees/minimind-job-agent/tests/evals/test_retrieval_runner.py::test_write_retrieval_report_creates_report_files -v`
Expected: FAIL because the CLI/report helper does not exist yet.

- [ ] **Step 3: Implement the CLI**

Create `scripts/run_sales_copilot_retrieval_eval.py`:

```python
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from evals.sales_copilot.retrieval_runner import run_retrieval_benchmark


def write_retrieval_report(*, output_dir: Path, payload: dict) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_json = output_dir / "report.json"
    report_md = output_dir / "report.md"
    case_results_jsonl = output_dir / "case_results.jsonl"

    report_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    case_results_jsonl.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in payload["case_results"]) + "\n",
        encoding="utf-8",
    )

    summary = payload["summary"]
    report_md.write_text(
        "# Sales Copilot Retrieval Evaluation\n\n"
        f"- keyword_only Recall@1: {summary['keyword_only']['recall_at_1']}\n"
        f"- keyword_only Recall@3: {summary['keyword_only']['recall_at_3']}\n"
        f"- keyword_only MRR: {summary['keyword_only']['mrr']}\n"
        f"- hybrid Recall@1: {summary['hybrid']['recall_at_1']}\n"
        f"- hybrid Recall@3: {summary['hybrid']['recall_at_3']}\n"
        f"- hybrid MRR: {summary['hybrid']['mrr']}\n",
        encoding="utf-8",
    )

    return {
        "report_json": report_json,
        "report_md": report_md,
        "case_results_jsonl": case_results_jsonl,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", required=True)
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    payload = run_retrieval_benchmark(cases_path=args.cases, db_path=args.db_path)
    timestamp_dir = Path(args.output_dir) / datetime.now().strftime("%Y%m%d%H%M%S")
    paths = write_retrieval_report(output_dir=timestamp_dir, payload=payload)
    print(paths["report_md"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest D:/minimind/.worktrees/minimind-job-agent/tests/evals/test_retrieval_runner.py::test_write_retrieval_report_creates_report_files -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C D:/minimind/.worktrees/minimind-job-agent add scripts/run_sales_copilot_retrieval_eval.py tests/evals/test_retrieval_runner.py
git -C D:/minimind/.worktrees/minimind-job-agent commit -m "feat: add retrieval evaluation CLI"
```

### Task 5: Document the benchmark and run regression

**Files:**
- Modify: `D:/minimind/.worktrees/minimind-job-agent/README.md`
- Test: `D:/minimind/.worktrees/minimind-job-agent/tests/evals/test_retrieval_metrics.py`
- Test: `D:/minimind/.worktrees/minimind-job-agent/tests/evals/test_retrieval_runner.py`

- [ ] **Step 1: Update README**

Add a short section like:

```md
## Retrieval Benchmark

Sales Copilot includes a dedicated retrieval benchmark for the local product/playbook knowledge base.

It compares:
- `keyword_only`
- `hybrid`

Metrics:
- `Recall@1`
- `Recall@3`
- `Recall@5`
- `MRR`

Run:

```bash
python scripts/run_sales_copilot_retrieval_eval.py \
  --cases evals/sales_copilot/retrieval_cases.jsonl \
  --db-path data/sales_copilot/sales_copilot.db \
  --output-dir evals/sales_copilot/outputs_retrieval
```
```

- [ ] **Step 2: Run focused retrieval evaluation tests**

Run: `pytest D:/minimind/.worktrees/minimind-job-agent/tests/evals/test_retrieval_metrics.py D:/minimind/.worktrees/minimind-job-agent/tests/evals/test_retrieval_runner.py -q`
Expected: PASS

- [ ] **Step 3: Run broader eval regression**

Run: `pytest D:/minimind/.worktrees/minimind-job-agent/tests/evals -q`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git -C D:/minimind/.worktrees/minimind-job-agent add README.md
git -C D:/minimind/.worktrees/minimind-job-agent commit -m "docs: add retrieval benchmark usage"
```
