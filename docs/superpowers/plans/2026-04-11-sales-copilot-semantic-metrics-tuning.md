# Sales Copilot Semantic Metrics Tuning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve semantic metric usefulness by letting loose literal matches bypass field guards and by measuring a small threshold sweep on the AI-calibrated benchmark.

**Architecture:** Keep the existing semantic metric framework, but change scoring order inside `metrics.py` so literal/loose title matches get full credit before semantic guard filtering. After the code change, run a small scripted sweep over the most ambiguous field thresholds and compare the resulting semantic summary metrics.

**Tech Stack:** Python, pytest, existing Sales Copilot eval pipeline

---

### Task 1: Add a failing test for literal-match precedence

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_sales_copilot_metrics.py`
- Test: `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_sales_copilot_metrics.py`

- [ ] **Step 1: Write the failing test**

```python
def test_evaluate_parse_case_semantic_literal_match_bypasses_field_guard():
    case = {
        "expected_parse": {
            "account_name": "BluePeak Health",
            "customer_roles": [],
            "confirmed_needs": [],
            "budget_signals": ["shipping credit request"],
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
        "budget_signals": ["request for shipping credit"],
        "timeline_signals": [],
        "next_steps": [],
        "competitors": [],
        "risk_flags": [],
    }

    metrics = evaluate_parse_case(case, actual_parse)

    assert metrics["semantic_list_field_f1"]["budget_signals"] == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_sales_copilot_metrics.py::test_evaluate_parse_case_semantic_literal_match_bypasses_field_guard -q`

Expected: FAIL because the current semantic scorer applies the field guard before loose literal matching.

- [ ] **Step 3: Implement the minimal fix**

```python
def _semantic_similarity_score(...):
    if _task_title_matches(expected_item, actual_item):
        return 1.0
    if not _passes_semantic_field_guard(field, expected_item, actual_item):
        return -inf
    ...
```

- [ ] **Step 4: Run the focused test and the semantic metric test file**

Run:

```bash
pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_sales_copilot_metrics.py::test_evaluate_parse_case_semantic_literal_match_bypasses_field_guard -q
pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_sales_copilot_metrics.py -q
```

Expected: PASS.


### Task 2: Run a small semantic threshold sweep

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\metrics.py`
- Output only: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_csds_ai_calibrated_eval_semantic\...`

- [ ] **Step 1: Set candidate thresholds for ambiguous fields**

Test these field values while leaving other thresholds unchanged:

```python
{
    "budget_signals": 0.72,
    "timeline_signals": 0.70,
    "next_steps": 0.68,
}
```

- [ ] **Step 2: Run the AI-calibrated benchmark once with the updated thresholds**

Run:

```bash
$env:DEEPSEEK_API_KEY="<set in shell>"
& 'D:\anaconda\envs\minimind_job_agent\python.exe' 'D:\minimind\.worktrees\minimind-job-agent\scripts\run_sales_copilot_eval.py' `
  --dataset-kind csds `
  --cases 'D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_csds_calibrated_100\full_csds_ai_calibrated_100.jsonl' `
  --output-dir 'D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_csds_ai_calibrated_eval_semantic_tuned'
```

- [ ] **Step 3: Compare the semantic summary to the previous baseline**

Read:

```bash
Get-Content D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_csds_ai_calibrated_eval_semantic_tuned\<timestamp>\report.json
```

Compare:
- `semantic_list_field_precision`
- `semantic_list_field_recall`
- `semantic_list_field_f1`
- `average_semantic_list_field_f1`

- [ ] **Step 4: Commit the tuning change if the code-level fix is verified**

```bash
git -C D:\minimind\.worktrees\minimind-job-agent add evals/sales_copilot/metrics.py tests/evals/test_sales_copilot_metrics.py docs/superpowers/plans/2026-04-11-sales-copilot-semantic-metrics-tuning.md
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "tune: relax semantic metric matching"
```
