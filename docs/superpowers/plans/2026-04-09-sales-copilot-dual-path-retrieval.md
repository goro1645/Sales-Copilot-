# Dual-Path Retrieval Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a dual-path retrieval benchmark for Sales Copilot that compares `gold-parse -> retrieval` against `model-parse -> retrieval`, reports the gap between them, and reuses the current keyword / hybrid / hybrid_rerank retrieval modes.

**Architecture:** Add a deterministic query builder that converts structured parse fields into retrieval queries, then extend the retrieval benchmark runner so the same case set can be evaluated through a gold-structured path and a model-parse path. Keep retrieval metrics unchanged (`Recall@1/3/5`, `MRR`), but add path-aware summaries, bucket summaries, and gap analysis in the report output.

**Tech Stack:** Python, pytest, LangGraph parse node reuse, DeepSeek client, JSONL benchmarks

---

## File Map

- Create: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\dual_path_query_builder.py`
  - Build deterministic retrieval queries from structured parse payloads.
- Modify: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\retrieval_runner.py`
  - Support dual-path execution and richer case payloads.
- Modify: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\retrieval_metrics.py`
  - Summarize path-level metrics and gold/model gap metrics.
- Modify: `D:\minimind\.worktrees\minimind-job-agent\scripts\run_sales_copilot_retrieval_eval.py`
  - Add dual-path CLI options and report rendering.
- Modify: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\retrieval_cases_csds_hard.jsonl`
  - Add minimal `gold_parse` payloads for dual-path query generation.
- Test: `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_dual_path_query_builder.py`
- Modify/Test: `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_retrieval_runner.py`
- Modify/Test: `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_retrieval_metrics.py`

### Task 1: Deterministic Query Builder

**Files:**
- Create: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\dual_path_query_builder.py`
- Test: `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_dual_path_query_builder.py`

- [ ] **Step 1: Write the failing tests**

```python
from evals.sales_copilot.dual_path_query_builder import build_retrieval_query


def test_build_retrieval_query_prioritizes_confirmed_needs_then_risk_and_next_steps():
    query = build_retrieval_query(
        {
            "confirmed_needs": ["private deployment", "audit logging"],
            "timeline_signals": ["security review this week"],
            "next_steps": ["schedule technical demo"],
            "risk_flags": ["security_review"],
        }
    )

    assert query == "private deployment audit logging security_review schedule technical demo security review this week"


def test_build_retrieval_query_skips_empty_fields_and_deduplicates_terms():
    query = build_retrieval_query(
        {
            "confirmed_needs": ["crm sync", "crm sync"],
            "timeline_signals": [],
            "next_steps": ["assign one owner"],
            "risk_flags": [],
        }
    )

    assert query == "crm sync assign one owner"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_dual_path_query_builder.py -v`
Expected: FAIL with `ModuleNotFoundError` or `ImportError` because `dual_path_query_builder.py` does not exist yet.

- [ ] **Step 3: Write the minimal implementation**

```python
from __future__ import annotations

from typing import Any

_QUERY_FIELDS = ("confirmed_needs", "risk_flags", "next_steps", "timeline_signals")


def _normalize_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def build_retrieval_query(parse_payload: dict[str, Any]) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for field in _QUERY_FIELDS:
        for item in _normalize_items(parse_payload.get(field, [])):
            if item in seen:
                continue
            seen.add(item)
            parts.append(item)
    return " ".join(parts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_dual_path_query_builder.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C D:\minimind\.worktrees\minimind-job-agent add evals/sales_copilot/dual_path_query_builder.py tests/evals/test_dual_path_query_builder.py
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "feat: add dual-path retrieval query builder"
```

### Task 2: Dual-Path Runner and Metrics

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\retrieval_runner.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\retrieval_metrics.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\retrieval_cases_csds_hard.jsonl`
- Modify/Test: `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_retrieval_runner.py`
- Modify/Test: `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_retrieval_metrics.py`

- [ ] **Step 1: Write the failing tests**

```python
from evals.sales_copilot.retrieval_runner import run_dual_path_retrieval_benchmark


def test_run_dual_path_retrieval_benchmark_reports_gold_and_model_paths(tmp_path, monkeypatch):
    payload = {
        "confirmed_needs": ["private deployment"],
        "next_steps": ["schedule demo"],
        "timeline_signals": [],
        "risk_flags": ["security_review"],
    }

    monkeypatch.setattr(
        "evals.sales_copilot.retrieval_runner._run_model_parse_for_case",
        lambda case, llm_client=None: payload,
    )

    results = run_dual_path_retrieval_benchmark(
        cases_path=tmp_path / "cases.jsonl",
        db_path=tmp_path / "sales.db",
        llm_client=object(),
    )

    assert "gold" in results["summary"]
    assert "model" in results["summary"]
    assert "gap" in results
```

```python
from evals.sales_copilot.retrieval_metrics import summarize_dual_path_gap


def test_summarize_dual_path_gap_subtracts_model_from_gold():
    gap = summarize_dual_path_gap(
        {
            "gold": {"keyword_only": {"recall_at_1": 0.8, "mrr": 0.9}},
            "model": {"keyword_only": {"recall_at_1": 0.5, "mrr": 0.7}},
        }
    )

    assert gap["keyword_only"]["recall_at_1_gap"] == 0.3
    assert gap["keyword_only"]["mrr_gap"] == 0.2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_retrieval_runner.py D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_retrieval_metrics.py -v`
Expected: FAIL because `run_dual_path_retrieval_benchmark` and `summarize_dual_path_gap` do not exist yet.

- [ ] **Step 3: Write the minimal implementation**

```python
# retrieval_runner.py
from evals.sales_copilot.dual_path_query_builder import build_retrieval_query
from evals.sales_copilot.csds_runner import _run_parse_step


def _run_model_parse_for_case(case, *, llm_client):
    csds_case = {
        "customer_profile_text": case["customer_profile_text"],
        "meeting_note_text": case["meeting_note_text"],
    }
    return _run_parse_step(csds_case, llm_client=llm_client)


def run_dual_path_retrieval_benchmark(*, cases_path, db_path, llm_client, top_k=5, embedder=_USE_DEFAULT_EMBEDDER, reranker=None):
    cases = load_retrieval_cases(cases_path)
    path_payloads = {"gold": [], "model": []}
    for case in cases:
        gold_query = build_retrieval_query(case["gold_parse"])
        model_parse = _run_model_parse_for_case(case, llm_client=llm_client)
        model_query = build_retrieval_query(model_parse)
        path_payloads["gold"].append(_evaluate_case(case, gold_query, db_path, top_k=top_k, embedder=embedder, reranker=reranker))
        path_payloads["model"].append(_evaluate_case(case, model_query, db_path, top_k=top_k, embedder=embedder, reranker=reranker, model_parse=model_parse))
    return {
        "summary": summarize_dual_path_metrics(path_payloads),
        "bucket_summary": summarize_dual_path_metrics_by_bucket(path_payloads),
        "gap": summarize_dual_path_gap(summarize_dual_path_metrics(path_payloads)),
        "case_results": path_payloads,
    }
```

```python
# retrieval_metrics.py
def summarize_dual_path_gap(summary_by_path: dict[str, dict[str, dict[str, float]]]) -> dict[str, dict[str, float]]:
    gold = summary_by_path.get("gold", {})
    model = summary_by_path.get("model", {})
    gap: dict[str, dict[str, float]] = {}
    for mode, gold_metrics in gold.items():
        model_metrics = model.get(mode, {})
        gap[mode] = {
            "recall_at_1_gap": gold_metrics.get("recall_at_1", 0.0) - model_metrics.get("recall_at_1", 0.0),
            "recall_at_3_gap": gold_metrics.get("recall_at_3", 0.0) - model_metrics.get("recall_at_3", 0.0),
            "recall_at_5_gap": gold_metrics.get("recall_at_5", 0.0) - model_metrics.get("recall_at_5", 0.0),
            "mrr_gap": gold_metrics.get("mrr", 0.0) - model_metrics.get("mrr", 0.0),
        }
    return gap
```

- [ ] **Step 4: Add minimal dual-path fields to the benchmark dataset**

```json
{
  "case_id": "csds_product_001",
  "query": "legacy benchmark field kept for backward compatibility",
  "source_type": "product",
  "gold_parse": {
    "confirmed_needs": ["account memory", "follow-up actions"],
    "next_steps": ["keep history readable"],
    "timeline_signals": [],
    "risk_flags": []
  }
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_retrieval_runner.py D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_retrieval_metrics.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git -C D:\minimind\.worktrees\minimind-job-agent add evals/sales_copilot/retrieval_runner.py evals/sales_copilot/retrieval_metrics.py evals/sales_copilot/retrieval_cases_csds_hard.jsonl tests/evals/test_retrieval_runner.py tests/evals/test_retrieval_metrics.py
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "feat: add dual-path retrieval benchmark core"
```

### Task 3: CLI and Report Output

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\scripts\run_sales_copilot_retrieval_eval.py`
- Modify/Test: `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_retrieval_runner.py`

- [ ] **Step 1: Write the failing tests**

```python
from scripts.run_sales_copilot_retrieval_eval import _build_report_markdown


def test_dual_path_report_renders_gold_model_and_gap_sections():
    report = _build_report_markdown(
        {
            "report_kind": "dual_path",
            "summary": {"gold": {"keyword_only": {"recall_at_1": 1.0}}, "model": {"keyword_only": {"recall_at_1": 0.5}}},
            "gap": {"keyword_only": {"recall_at_1_gap": 0.5}},
            "case_results": [],
        }
    )

    assert "Gold Retrieval" in report
    assert "Model Retrieval" in report
    assert "Gap Analysis" in report
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_retrieval_runner.py -v`
Expected: FAIL because the markdown renderer does not yet know about `dual_path`.

- [ ] **Step 3: Write the minimal implementation**

```python
def _build_report_markdown(payload):
    if payload.get("report_kind") == "dual_path":
        return "\n".join(
            [
                "# Sales Copilot Dual-Path Retrieval Eval Report",
                "",
                "## Gold Retrieval",
                json.dumps(payload.get("summary", {}).get("gold", {}), ensure_ascii=False, indent=2),
                "",
                "## Model Retrieval",
                json.dumps(payload.get("summary", {}).get("model", {}), ensure_ascii=False, indent=2),
                "",
                "## Gap Analysis",
                json.dumps(payload.get("gap", {}), ensure_ascii=False, indent=2),
            ]
        )
    ...
```

- [ ] **Step 4: Run tests and a targeted benchmark smoke check**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals -q`
Expected: PASS

Run: `python D:\minimind\.worktrees\minimind-job-agent\scripts\run_sales_copilot_retrieval_eval.py --cases D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\retrieval_cases_csds_hard.jsonl --db-path D:\minimind\.worktrees\minimind-job-agent\data\sales_copilot\sales_copilot.db --output-dir D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_retrieval_dual`
Expected: prints a timestamped report directory with `report.json`, `report.md`, and `case_results.jsonl`.

- [ ] **Step 5: Commit**

```bash
git -C D:\minimind\.worktrees\minimind-job-agent add scripts/run_sales_copilot_retrieval_eval.py tests/evals/test_retrieval_runner.py
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "feat: add dual-path retrieval reporting"
```

## Self-Review

- Spec coverage:
  - dual-path query generation: Task 1
  - shared query builder across gold/model: Task 1 + Task 2
  - gold/model path execution: Task 2
  - bucket metrics and gap analysis: Task 2
  - report sections for gold/model/gap: Task 3
- Placeholder scan:
  - removed `TODO`/`TBD`
  - every task includes concrete files, commands, and code snippets
- Type consistency:
  - `gold_parse` is the shared structured payload name across dataset, query builder, and runner
  - `run_dual_path_retrieval_benchmark` and `summarize_dual_path_gap` names are used consistently throughout
