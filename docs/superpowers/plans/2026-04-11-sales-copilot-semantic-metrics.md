# Sales Copilot Semantic Metrics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add semantic list-field precision/recall/F1 metrics that better reward semantic equivalence while preserving the existing literal parse metrics.

**Architecture:** Keep the legacy parse metrics intact and compute a parallel semantic layer inside `evals/sales_copilot/metrics.py`. The semantic layer will embed gold/predicted list items, apply field-specific semantic guards, do one-to-one best matching, and surface both per-case and summary metrics through the normal reporting pipeline.

**Tech Stack:** Python, pytest, sentence-transformers, NumPy, existing Sales Copilot eval/reporting utilities

---

### Task 1: Add failing semantic-metric tests

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_sales_copilot_metrics.py`
- Test: `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_sales_copilot_metrics.py`

- [ ] **Step 1: Write failing tests for semantic paraphrase matching and field guards**

```python
from unittest.mock import patch


def test_evaluate_parse_case_adds_semantic_match_for_paraphrases():
    case = {
        "expected_parse": {
            "account_name": "BluePeak Health",
            "customer_roles": [],
            "confirmed_needs": ["need private deployment with audit trail"],
            "budget_signals": [],
            "timeline_signals": [],
            "next_steps": ["follow up after carrier review"],
            "competitors": [],
        },
        "expected_workflow": {"required_risk_flags": []},
    }
    actual_parse = {
        "account_name": "BluePeak Health",
        "customer_roles": [],
        "confirmed_needs": ["wants on-prem deployment and audit logging"],
        "budget_signals": [],
        "timeline_signals": [],
        "next_steps": ["contact carrier, verify issue, then reply"],
        "competitors": [],
        "risk_flags": [],
    }

    fake_vectors = {
        "need private deployment with audit trail": [1.0, 0.0],
        "wants on-prem deployment and audit logging": [0.99, 0.01],
        "follow up after carrier review": [0.0, 1.0],
        "contact carrier, verify issue, then reply": [0.0, 0.99],
    }

    class _FakeEmbedder:
        model_name = "fake-semantic"

        def embed_texts(self, texts):
            return [fake_vectors[text] for text in texts]

    with patch("evals.sales_copilot.metrics.load_default_embedder", return_value=_FakeEmbedder()):
        metrics = evaluate_parse_case(case, actual_parse)

    assert metrics["semantic_list_field_f1"]["confirmed_needs"] == 1.0
    assert metrics["semantic_list_field_f1"]["next_steps"] == 1.0


def test_evaluate_parse_case_semantic_guards_block_cross_field_false_positive():
    case = {
        "expected_parse": {
            "account_name": "BluePeak Health",
            "customer_roles": [],
            "confirmed_needs": [],
            "budget_signals": ["refund coupon difference"],
            "timeline_signals": [],
            "next_steps": [],
            "competitors": [],
        },
        "expected_workflow": {"required_risk_flags": []},
    }
    actual_parse = {
        "account_name": "BluePeak Health",
        "customer_roles": [],
        "confirmed_needs": [],
        "budget_signals": ["contact support tomorrow"],
        "timeline_signals": [],
        "next_steps": [],
        "competitors": [],
        "risk_flags": [],
    }

    fake_vectors = {
        "refund coupon difference": [1.0, 0.0],
        "contact support tomorrow": [1.0, 0.0],
    }

    class _FakeEmbedder:
        model_name = "fake-semantic"

        def embed_texts(self, texts):
            return [fake_vectors[text] for text in texts]

    with patch("evals.sales_copilot.metrics.load_default_embedder", return_value=_FakeEmbedder()):
        metrics = evaluate_parse_case(case, actual_parse)

    assert metrics["semantic_list_field_recall"]["budget_signals"] == 0.0


def test_summarize_parse_metrics_includes_semantic_summary_values():
    rows = [
        {
            "json_valid": True,
            "field_exact_match": {"account_name": True},
            "list_field_precision": {field: 0.0 for field in ("customer_roles", "confirmed_needs", "budget_signals", "timeline_signals", "next_steps", "competitors")},
            "list_field_recall": {field: 0.0 for field in ("customer_roles", "confirmed_needs", "budget_signals", "timeline_signals", "next_steps", "competitors")},
            "list_field_f1": {field: 0.0 for field in ("customer_roles", "confirmed_needs", "budget_signals", "timeline_signals", "next_steps", "competitors")},
            "semantic_list_field_precision": {"confirmed_needs": 1.0},
            "semantic_list_field_recall": {"confirmed_needs": 1.0},
            "semantic_list_field_f1": {"confirmed_needs": 1.0},
            "list_field_applicable": {field: field == "confirmed_needs" for field in ("customer_roles", "confirmed_needs", "budget_signals", "timeline_signals", "next_steps", "competitors")},
            "semantic_list_field_applicable": {field: field == "confirmed_needs" for field in ("customer_roles", "confirmed_needs", "budget_signals", "timeline_signals", "next_steps", "competitors")},
            "risk_flag_recall": 0.0,
            "risk_flag_applicable": False,
        }
    ]

    summary = summarize_parse_metrics(rows)

    assert summary["semantic_list_field_precision"] == 1.0
    assert summary["semantic_list_field_recall"] == 1.0
    assert summary["semantic_list_field_f1"] == 1.0
    assert summary["average_semantic_list_field_f1"] == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_sales_copilot_metrics.py -q`

Expected: FAIL because semantic metric keys and semantic matcher logic do not exist yet.

- [ ] **Step 3: Commit the failing-test checkpoint if you want an explicit red snapshot**

```bash
git -C D:\minimind\.worktrees\minimind-job-agent add tests/evals/test_sales_copilot_metrics.py
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "test: cover semantic parse metrics"
```


### Task 2: Implement semantic matching and parse-metric aggregation

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\metrics.py`
- Test: `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_sales_copilot_metrics.py`

- [ ] **Step 1: Add semantic helper constants and guards**

```python
SEMANTIC_FIELD_THRESHOLDS = {
    "customer_roles": 0.84,
    "confirmed_needs": 0.80,
    "budget_signals": 0.78,
    "timeline_signals": 0.78,
    "next_steps": 0.78,
    "competitors": 0.82,
}

FIELD_GUARD_MARKERS = {
    "budget_signals": ("refund", "coupon", "discount", "price", "fee", "退款", "优惠券", "差价", "补偿", "价格", "价保"),
    "timeline_signals": ("today", "tomorrow", "after", "within", "business day", "今天", "明天", "之后", "完成后", "工作日内", "稍后", "尽快"),
    "next_steps": ("contact", "submit", "apply", "modify", "reorder", "return", "联系", "提交", "申请", "修改", "重新下单", "寄回", "回复", "处理"),
}
```

- [ ] **Step 2: Add semantic normalization, guard, and one-to-one matching helpers**

```python
def _semantic_normalize_text(value: Any) -> str:
    text = _normalize_text(value)
    return re.sub(r"[\\s\\u3000]+", " ", text).strip()


def _passes_field_guard(field: str, gold_item: str, actual_item: str) -> bool:
    markers = FIELD_GUARD_MARKERS.get(field)
    if not markers:
        return True
    gold_text = _semantic_normalize_text(gold_item)
    actual_text = _semantic_normalize_text(actual_item)
    return any(marker in gold_text for marker in markers) and any(marker in actual_text for marker in markers)


def _semantic_set_precision_recall_f1(field: str, expected: list[str], actual: list[str]) -> tuple[float, float, float]:
    ...
```
```

- [ ] **Step 3: Wire semantic metrics into `evaluate_parse_case` and invalid-path output**

```python
return {
    "json_valid": True,
    "field_exact_match": field_exact_match,
    "list_field_precision": list_field_precision,
    "list_field_recall": list_field_recall,
    "list_field_f1": list_field_f1,
    "semantic_list_field_precision": semantic_list_field_precision,
    "semantic_list_field_recall": semantic_list_field_recall,
    "semantic_list_field_f1": semantic_list_field_f1,
    "list_field_applicable": list_field_applicable,
    "semantic_list_field_applicable": semantic_list_field_applicable,
    "risk_flag_recall": risk_flag_recall,
    "risk_flag_applicable": risk_flag_applicable,
}
```

- [ ] **Step 4: Extend `summarize_parse_metrics` to aggregate semantic metrics**

```python
return {
    "json_valid_rate": json_valid_rate,
    "field_exact_match_rate": field_exact_match_rate,
    "list_field_precision": list_field_precision_average,
    "list_field_recall": list_field_recall_average,
    "list_field_f1": list_field_f1_average,
    "average_list_field_f1": average_list_field_f1,
    "semantic_list_field_precision": semantic_list_field_precision_average,
    "semantic_list_field_recall": semantic_list_field_recall_average,
    "semantic_list_field_f1": semantic_list_field_f1_average,
    "average_semantic_list_field_f1": average_semantic_list_field_f1,
    "risk_flag_recall": risk_flag_recall,
}
```

- [ ] **Step 5: Run tests to verify green**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_sales_copilot_metrics.py -q`

Expected: PASS with all semantic metric tests green.

- [ ] **Step 6: Commit the semantic metric core**

```bash
git -C D:\minimind\.worktrees\minimind-job-agent add evals/sales_copilot/metrics.py tests/evals/test_sales_copilot_metrics.py
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "feat: add semantic parse metrics"
```


### Task 3: Expose semantic metrics in reports and verify on calibrated data

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\reporting.py`
- Create or Modify: `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_reporting.py`
- Test: `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_reporting.py`

- [ ] **Step 1: Add a failing reporting test**

```python
from evals.sales_copilot.reporting import _build_report_markdown


def test_build_report_markdown_includes_semantic_parse_metrics():
    bundle = {
        "summary": {
            "total_cases": 1,
            "parse": {
                "json_valid_rate": 1.0,
                "list_field_precision": 0.5,
                "list_field_recall": 0.5,
                "list_field_f1": 0.5,
                "average_list_field_f1": 0.5,
                "semantic_list_field_precision": 0.9,
                "semantic_list_field_recall": 0.8,
                "semantic_list_field_f1": 0.85,
                "average_semantic_list_field_f1": 0.86,
                "risk_flag_recall": 0.0,
                "field_exact_match_rate": {"account_name": 1.0},
            },
            "workflow": {},
        },
        "report_kind": "parse_only",
        "case_results": [],
    }

    markdown = _build_report_markdown(bundle)

    assert "semantic_list_field_precision" in markdown
    assert "average_semantic_list_field_f1" in markdown
```

- [ ] **Step 2: Run the reporting test and verify red**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_reporting.py -q`

Expected: FAIL because markdown output does not list semantic metrics yet.

- [ ] **Step 3: Add semantic metrics to parse report markdown**

```python
for key in (
    "json_valid_rate",
    "list_field_precision",
    "list_field_recall",
    "list_field_f1",
    "average_list_field_f1",
    "semantic_list_field_precision",
    "semantic_list_field_recall",
    "semantic_list_field_f1",
    "average_semantic_list_field_f1",
    "risk_flag_recall",
):
    lines.append(f"| {key} | {parse_summary.get(key, 'N/A')} |")
```

- [ ] **Step 4: Run targeted tests and then the broader eval suite**

Run:

```bash
pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_sales_copilot_metrics.py D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_reporting.py -q
pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals -q
```

Expected:
- targeted tests all PASS
- broader eval suite PASS

- [ ] **Step 5: Run a live parse-only eval on the AI-calibrated benchmark**

Run:

```bash
$env:DEEPSEEK_API_KEY="<set in shell>"
& 'D:\anaconda\envs\minimind_job_agent\python.exe' 'D:\minimind\.worktrees\minimind-job-agent\scripts\run_sales_copilot_eval.py' `
  --cases 'D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_csds_calibrated_100\full_csds_ai_calibrated_100.jsonl' `
  --output-dir 'D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_csds_ai_calibrated_eval_semantic' `
  --report-kind parse_only
```

Expected:
- command exits `0`
- new `report.json` and `report.md` include the semantic metric keys

- [ ] **Step 6: Commit the reporting integration**

```bash
git -C D:\minimind\.worktrees\minimind-job-agent add evals/sales_copilot/reporting.py tests/evals/test_reporting.py docs/superpowers/specs/2026-04-11-sales-copilot-semantic-metrics-design.md docs/superpowers/plans/2026-04-11-sales-copilot-semantic-metrics.md
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "feat: report semantic parse metrics"
```

## Self-Review

- Spec coverage: semantic per-case metrics, semantic summary metrics, field guards, report output, and calibrated-set execution are all mapped to Tasks 1-3.
- Placeholder scan: no TBD/TODO placeholders remain; each task includes exact files, test commands, and concrete code shape.
- Type consistency: all new payload keys use the same names across plan tasks:
  - `semantic_list_field_precision`
  - `semantic_list_field_recall`
  - `semantic_list_field_f1`
  - `semantic_list_field_applicable`
  - `average_semantic_list_field_f1`

Plan complete and saved to `D:\minimind\.worktrees\minimind-job-agent\docs\superpowers\plans\2026-04-11-sales-copilot-semantic-metrics.md`. The user already requested inline execution, so proceed with `executing-plans` in this session.
