# Sales Copilot Offline Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a repeatable offline benchmark for `Sales Copilot` that scores parse quality and workflow quality on a local golden dataset and writes JSON/Markdown reports.

**Architecture:** Add a focused `evals/sales_copilot` package with case loading, pure metric functions, a runner that reuses the existing parse and workflow entry points, and report writers. Keep benchmark data in JSONL, use fake LLMs in tests, seed a fresh SQLite database for every evaluated case, and expose one CLI that runs the full benchmark and writes artifacts to `evals/sales_copilot/outputs/`.

**Tech Stack:** Python, pytest, JSONL, Markdown reporting, SQLite, LangGraph workflow hooks, `DeepSeekClient`

---

## File Map

- `evals/sales_copilot/__init__.py`
  - evaluation package exports
- `evals/sales_copilot/cases.py`
  - golden-case types, validation, JSONL loading
- `evals/sales_copilot/metrics.py`
  - pure parse metrics and workflow metrics
- `evals/sales_copilot/runner.py`
  - run parse pass + workflow pass for each case, seed per-case DBs
- `evals/sales_copilot/reporting.py`
  - write `report.json`, `report.md`, and `case_results.jsonl`
- `evals/sales_copilot/golden_cases.jsonl`
  - 16 benchmark cases across four segments
- `scripts/run_sales_copilot_eval.py`
  - CLI entry point for the benchmark
- `tests/evals/test_sales_copilot_cases.py`
  - loader and dataset validation tests
- `tests/evals/test_sales_copilot_metrics.py`
  - metric function tests
- `tests/evals/test_sales_copilot_runner.py`
  - runner and reporting tests
- `README.md`
  - evaluation quickstart and output description

### Task 1: Evaluation Package Scaffold And Case Loader

**Files:**
- Create: `evals/sales_copilot/__init__.py`
- Create: `evals/sales_copilot/cases.py`
- Create: `evals/sales_copilot/golden_cases.jsonl`
- Create: `tests/evals/test_sales_copilot_cases.py`

- [ ] **Step 1: Write the failing case-loader tests**

```python
from pathlib import Path

import pytest

from evals.sales_copilot.cases import load_golden_cases


VALID_CASES = """\
{"case_id":"manufacturing_complete_001","segment":"high_intent_complete","customer_profile_text":"Account: Acme Robotics","meeting_note_text":"CTO approved a private deployment pilot this quarter.","expected_parse":{"account_name":"Acme Robotics","customer_roles":["CTO"],"confirmed_needs":["private deployment"],"budget_signals":["pilot approved"],"timeline_signals":["this quarter"],"next_steps":["schedule technical demo"],"competitors":[]},"expected_workflow":{"lead_score_range":[80,95],"lead_priority":"high","opportunity_stage":"proposal","expected_route":"high_priority_follow_up","should_write_crm":true,"should_generate_tasks":true,"required_task_titles":["schedule technical demo"],"required_risk_flags":[]}}
{"case_id":"noise_001","segment":"low_intent_or_noise","customer_profile_text":"Account: Riverside Foods","meeting_note_text":"The buyer asked for a generic brochure and had no active project timeline this quarter.","expected_parse":{"account_name":"Riverside Foods","customer_roles":["Buyer"],"confirmed_needs":["brochure"],"budget_signals":[],"timeline_signals":[],"next_steps":["send brochure"],"competitors":[]},"expected_workflow":{"lead_score_range":[0,35],"lead_priority":"low","opportunity_stage":"discovery","expected_route":"low_priority_nurture","should_write_crm":true,"should_generate_tasks":false,"required_task_titles":[],"required_risk_flags":[]}}
"""


def test_load_golden_cases_returns_validated_payloads(tmp_path: Path):
    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(VALID_CASES, encoding="utf-8")

    cases = load_golden_cases(cases_path)

    assert len(cases) == 2
    assert cases[0]["case_id"] == "manufacturing_complete_001"
    assert cases[1]["expected_workflow"]["expected_route"] == "low_priority_nurture"


def test_load_golden_cases_rejects_missing_required_workflow_fields(tmp_path: Path):
    invalid_path = tmp_path / "bad_cases.jsonl"
    invalid_path.write_text(
        '{"case_id":"bad_001","segment":"high_intent_complete","customer_profile_text":"a","meeting_note_text":"b","expected_parse":{"account_name":"A","customer_roles":[],"confirmed_needs":[],"budget_signals":[],"timeline_signals":[],"next_steps":[],"competitors":[]},"expected_workflow":{"lead_score_range":[80,95]}}\\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="required_workflow_fields"):
        load_golden_cases(invalid_path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest tests/evals/test_sales_copilot_cases.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'evals.sales_copilot'` or import errors for `load_golden_cases`

- [ ] **Step 3: Write the minimal case package, loader, and initial 4-case dataset**

```python
# evals/sales_copilot/__init__.py
from .cases import GoldenCase, load_golden_cases

__all__ = ["GoldenCase", "load_golden_cases"]
```

```python
# evals/sales_copilot/cases.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict


class ExpectedParse(TypedDict):
    account_name: str
    customer_roles: list[str]
    confirmed_needs: list[str]
    budget_signals: list[str]
    timeline_signals: list[str]
    next_steps: list[str]
    competitors: list[str]


class ExpectedWorkflow(TypedDict):
    lead_score_range: list[int]
    lead_priority: str
    opportunity_stage: str
    expected_route: str
    should_write_crm: bool
    should_generate_tasks: bool
    required_task_titles: list[str]
    required_risk_flags: list[str]


class GoldenCase(TypedDict):
    case_id: str
    segment: str
    customer_profile_text: str
    meeting_note_text: str
    expected_parse: ExpectedParse
    expected_workflow: ExpectedWorkflow


REQUIRED_PARSE_FIELDS = {
    "account_name",
    "customer_roles",
    "confirmed_needs",
    "budget_signals",
    "timeline_signals",
    "next_steps",
    "competitors",
}
REQUIRED_WORKFLOW_FIELDS = {
    "lead_score_range",
    "lead_priority",
    "opportunity_stage",
    "expected_route",
    "should_write_crm",
    "should_generate_tasks",
    "required_task_titles",
    "required_risk_flags",
}


def _require_fields(payload: dict[str, Any], required: set[str], label: str) -> None:
    missing = sorted(required - set(payload))
    if missing:
        raise ValueError(f"{label} missing required_{label}_fields: {', '.join(missing)}")


def validate_golden_case(payload: dict[str, Any]) -> GoldenCase:
    _require_fields(payload, {"case_id", "segment", "customer_profile_text", "meeting_note_text", "expected_parse", "expected_workflow"}, "top_level")
    expected_parse = payload["expected_parse"]
    expected_workflow = payload["expected_workflow"]
    if not isinstance(expected_parse, dict):
        raise ValueError("expected_parse must be a dict")
    if not isinstance(expected_workflow, dict):
        raise ValueError("expected_workflow must be a dict")
    _require_fields(expected_parse, REQUIRED_PARSE_FIELDS, "parse")
    _require_fields(expected_workflow, REQUIRED_WORKFLOW_FIELDS, "workflow")
    return payload  # type: ignore[return-value]


def load_golden_cases(path: str | Path) -> list[GoldenCase]:
    rows: list[GoldenCase] = []
    case_path = Path(path)
    for line_number, line in enumerate(case_path.read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON on line {line_number}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"case line {line_number} must be a JSON object")
        rows.append(validate_golden_case(payload))
    return rows
```

```json
{"case_id":"manufacturing_complete_001","segment":"high_intent_complete","customer_profile_text":"Account: Acme Robotics\nIndustry: Manufacturing\nCurrent stage: Discovery","meeting_note_text":"The CTO approved a private deployment pilot, confirmed SSO and audit logging, and asked for a technical demo this quarter.","expected_parse":{"account_name":"Acme Robotics","customer_roles":["CTO"],"confirmed_needs":["private deployment","SSO","audit logging"],"budget_signals":["pilot approved"],"timeline_signals":["this quarter"],"next_steps":["schedule technical demo"],"competitors":[]},"expected_workflow":{"lead_score_range":[80,95],"lead_priority":"high","opportunity_stage":"proposal","expected_route":"high_priority_follow_up","should_write_crm":true,"should_generate_tasks":true,"required_task_titles":["schedule technical demo"],"required_risk_flags":[]}}
{"case_id":"healthcare_missing_001","segment":"high_intent_missing_facts","customer_profile_text":"Account: BluePeak Health\nIndustry: Healthcare\nCurrent stage: Qualification","meeting_note_text":"The CIO wants private deployment, audit logging, and CRM integration. The team asked for a workshop but did not confirm the timeline.","expected_parse":{"account_name":"BluePeak Health","customer_roles":["CIO"],"confirmed_needs":["private deployment","audit logging","CRM integration"],"budget_signals":[],"timeline_signals":[],"next_steps":["schedule workshop"],"competitors":[]},"expected_workflow":{"lead_score_range":[70,85],"lead_priority":"high","opportunity_stage":"qualification","expected_route":"standard_follow_up","should_write_crm":true,"should_generate_tasks":true,"required_task_titles":["confirm decision timeline","clarify qualification gaps"],"required_risk_flags":["missing_required_facts"]}}
{"case_id":"retail_nurture_001","segment":"medium_intent_nurture","customer_profile_text":"Account: Northwind Traders\nIndustry: Retail\nCurrent stage: Discovery","meeting_note_text":"The operations manager is curious about lead dashboards but has no budget owner yet and wants more educational material before a formal evaluation.","expected_parse":{"account_name":"Northwind Traders","customer_roles":["Operations Manager"],"confirmed_needs":["lead dashboards"],"budget_signals":[],"timeline_signals":[],"next_steps":["send educational material"],"competitors":[]},"expected_workflow":{"lead_score_range":[35,49],"lead_priority":"low","opportunity_stage":"discovery","expected_route":"low_priority_nurture","should_write_crm":true,"should_generate_tasks":false,"required_task_titles":[],"required_risk_flags":[]}}
{"case_id":"noise_001","segment":"low_intent_or_noise","customer_profile_text":"Account: Riverside Foods\nIndustry: Food Processing\nCurrent stage: Discovery","meeting_note_text":"The buyer only asked for a generic brochure and said there is no active project timeline this quarter.","expected_parse":{"account_name":"Riverside Foods","customer_roles":["Buyer"],"confirmed_needs":["brochure"],"budget_signals":[],"timeline_signals":[],"next_steps":["send brochure"],"competitors":[]},"expected_workflow":{"lead_score_range":[0,35],"lead_priority":"low","opportunity_stage":"discovery","expected_route":"low_priority_nurture","should_write_crm":true,"should_generate_tasks":false,"required_task_titles":[],"required_risk_flags":[]}}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest tests/evals/test_sales_copilot_cases.py -q`

Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add evals/sales_copilot/__init__.py evals/sales_copilot/cases.py evals/sales_copilot/golden_cases.jsonl tests/evals/test_sales_copilot_cases.py
git commit -m "feat: add sales copilot eval case loader"
```

### Task 2: Parse Metrics

**Files:**
- Create: `evals/sales_copilot/metrics.py`
- Create: `tests/evals/test_sales_copilot_metrics.py`

- [ ] **Step 1: Write the failing parse-metric tests**

```python
from evals.sales_copilot.metrics import evaluate_parse_case, summarize_parse_metrics


def test_evaluate_parse_case_scores_scalar_and_list_fields():
    case = {
        "expected_parse": {
            "account_name": "BluePeak Health",
            "customer_roles": ["CIO", "Compliance Manager"],
            "confirmed_needs": ["private deployment", "audit logging"],
            "budget_signals": ["pilot approved"],
            "timeline_signals": [],
            "next_steps": ["schedule workshop"],
            "competitors": [],
        }
    }
    actual = {
        "account_name": "BluePeak Health",
        "customer_roles": ["CIO"],
        "confirmed_needs": ["private deployment", "audit logging"],
        "budget_signals": ["pilot approved"],
        "timeline_signals": [],
        "next_steps": ["schedule workshop"],
        "competitors": [],
    }

    metrics = evaluate_parse_case(case, actual)

    assert metrics["json_valid"] is True
    assert metrics["field_exact_matches"]["account_name"] is True
    assert metrics["list_field_f1"]["customer_roles"] < 1.0
    assert metrics["list_field_f1"]["confirmed_needs"] == 1.0


def test_summarize_parse_metrics_aggregates_json_validity_and_average_f1():
    summary = summarize_parse_metrics(
        [
            {"json_valid": True, "field_exact_matches": {"account_name": True}, "list_field_f1": {"confirmed_needs": 1.0}, "risk_flag_recall": 1.0},
            {"json_valid": False, "field_exact_matches": {"account_name": False}, "list_field_f1": {"confirmed_needs": 0.0}, "risk_flag_recall": 0.0},
        ]
    )

    assert summary["json_valid_rate"] == 0.5
    assert summary["field_exact_match_rate"]["account_name"] == 0.5
    assert summary["average_list_field_f1"] == 0.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest tests/evals/test_sales_copilot_metrics.py -q`

Expected: FAIL with `ModuleNotFoundError` or missing metric function names

- [ ] **Step 3: Write minimal parse-metric implementation**

```python
# evals/sales_copilot/metrics.py
from __future__ import annotations

from typing import Any


PARSE_LIST_FIELDS = (
    "customer_roles",
    "confirmed_needs",
    "budget_signals",
    "timeline_signals",
    "next_steps",
    "competitors",
)


def _normalize_text(value: Any) -> str:
    return str(value).strip().lower()


def _normalize_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    cleaned = [_normalize_text(value) for value in values if _normalize_text(value)]
    return sorted(dict.fromkeys(cleaned))


def _list_precision_recall_f1(expected: list[str], actual: list[str]) -> tuple[float, float, float]:
    expected_set = set(expected)
    actual_set = set(actual)
    if not expected_set and not actual_set:
        return 1.0, 1.0, 1.0
    if not actual_set:
        return 0.0, 0.0, 0.0
    true_positive = len(expected_set & actual_set)
    precision = true_positive / len(actual_set)
    recall = true_positive / len(expected_set) if expected_set else 1.0
    if precision + recall == 0:
        return precision, recall, 0.0
    return precision, recall, 2 * precision * recall / (precision + recall)


def _recall(expected: list[str], actual: list[str]) -> float:
    if not expected:
        return 1.0
    expected_set = set(expected)
    actual_set = set(actual)
    return len(expected_set & actual_set) / len(expected_set)


def evaluate_parse_case(case: dict[str, Any], actual_parse: dict[str, Any] | None) -> dict[str, Any]:
    expected = case["expected_parse"]
    expected_risk_flags = _normalize_list(case.get("expected_workflow", {}).get("required_risk_flags", []))
    if not isinstance(actual_parse, dict):
        return {
            "json_valid": False,
            "field_exact_matches": {"account_name": False},
            "list_field_precision": {field: 0.0 for field in PARSE_LIST_FIELDS},
            "list_field_recall": {field: 0.0 for field in PARSE_LIST_FIELDS},
            "list_field_f1": {field: 0.0 for field in PARSE_LIST_FIELDS},
            "risk_flag_recall": 0.0,
        }

    field_exact_matches = {
        "account_name": _normalize_text(expected["account_name"]) == _normalize_text(actual_parse.get("account_name")),
    }
    list_field_precision: dict[str, float] = {}
    list_field_recall: dict[str, float] = {}
    list_field_f1: dict[str, float] = {}
    for field in PARSE_LIST_FIELDS:
        precision, recall, f1 = _list_precision_recall_f1(
            _normalize_list(expected.get(field, [])),
            _normalize_list(actual_parse.get(field, [])),
        )
        list_field_precision[field] = precision
        list_field_recall[field] = recall
        list_field_f1[field] = f1

    return {
        "json_valid": True,
        "field_exact_matches": field_exact_matches,
        "list_field_precision": list_field_precision,
        "list_field_recall": list_field_recall,
        "list_field_f1": list_field_f1,
        "risk_flag_recall": _recall(expected_risk_flags, _normalize_list(actual_parse.get("risk_flags", []))),
    }


def summarize_parse_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(rows) or 1
    field_rates: dict[str, float] = {}
    fields = {field for row in rows for field in row["field_exact_matches"]}
    for field in sorted(fields):
        field_rates[field] = sum(1.0 for row in rows if row["field_exact_matches"].get(field)) / count

    f1_values = [score for row in rows for score in row["list_field_f1"].values()]
    average_list_field_f1 = sum(f1_values) / len(f1_values) if f1_values else 0.0

    return {
        "json_valid_rate": sum(1.0 for row in rows if row["json_valid"]) / count,
        "field_exact_match_rate": field_rates,
        "average_list_field_f1": average_list_field_f1,
        "risk_flag_recall": sum(float(row["risk_flag_recall"]) for row in rows) / count,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest tests/evals/test_sales_copilot_metrics.py -q`

Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add evals/sales_copilot/metrics.py tests/evals/test_sales_copilot_metrics.py
git commit -m "feat: add sales copilot parse metrics"
```

### Task 3: Workflow Metrics

**Files:**
- Modify: `evals/sales_copilot/metrics.py`
- Modify: `tests/evals/test_sales_copilot_metrics.py`

- [ ] **Step 1: Write the failing workflow-metric tests**

```python
from evals.sales_copilot.metrics import evaluate_workflow_case, summarize_workflow_metrics


def test_evaluate_workflow_case_scores_route_score_range_crm_and_tasks():
    case = {
        "expected_workflow": {
            "lead_score_range": [70, 85],
            "lead_priority": "high",
            "opportunity_stage": "qualification",
            "expected_route": "standard_follow_up",
            "should_write_crm": True,
            "should_generate_tasks": True,
            "required_task_titles": ["confirm decision timeline", "clarify qualification gaps"],
            "required_risk_flags": ["missing_required_facts"],
        }
    }
    actual = {
        "lead_score": 75,
        "lead_priority": "high",
        "opportunity_stage": "qualification",
        "workflow_log": ["ingest_files", "parse_meeting_note", "standard_follow_up", "write_back_crm", "generate_dashboard_output"],
        "crm_update_ids": [1],
        "task_payload": [{"title": "Confirm decision timeline"}, {"title": "Clarify qualification gaps"}],
        "risk_flags": ["missing_required_facts"],
    }

    metrics = evaluate_workflow_case(case, actual)

    assert metrics["route_correct"] is True
    assert metrics["score_in_range"] is True
    assert metrics["crm_writeback_correct"] is True
    assert metrics["task_generation_correct"] is True
    assert metrics["required_task_hit_rate"] == 1.0


def test_summarize_workflow_metrics_aggregates_success_and_route_accuracy():
    summary = summarize_workflow_metrics(
        [
            {"workflow_success": True, "route_correct": True, "priority_correct": True, "stage_correct": True, "score_in_range": True, "crm_writeback_correct": True, "task_generation_correct": True, "required_task_hit_rate": 1.0},
            {"workflow_success": False, "route_correct": False, "priority_correct": False, "stage_correct": False, "score_in_range": False, "crm_writeback_correct": False, "task_generation_correct": False, "required_task_hit_rate": 0.0},
        ]
    )

    assert summary["workflow_success_rate"] == 0.5
    assert summary["route_accuracy"] == 0.5
    assert summary["required_task_hit_rate"] == 0.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest tests/evals/test_sales_copilot_metrics.py -q`

Expected: FAIL with missing `evaluate_workflow_case` or `summarize_workflow_metrics`

- [ ] **Step 3: Extend `metrics.py` with workflow scoring**

```python
# append to evals/sales_copilot/metrics.py
WORKFLOW_ROUTE_NAMES = (
    "need_more_info",
    "low_priority_nurture",
    "standard_follow_up",
    "high_priority_follow_up",
)


def _infer_route(workflow_log: list[str]) -> str:
    for item in workflow_log:
        if item in WORKFLOW_ROUTE_NAMES:
            return item
    return ""


def _normalize_titles(task_payload: Any) -> list[str]:
    if not isinstance(task_payload, list):
        return []
    titles: list[str] = []
    for item in task_payload:
        if isinstance(item, dict):
            title = _normalize_text(item.get("title", ""))
            if title:
                titles.append(title)
    return titles


def evaluate_workflow_case(case: dict[str, Any], actual_result: dict[str, Any] | None) -> dict[str, Any]:
    expected = case["expected_workflow"]
    if not isinstance(actual_result, dict):
        return {
            "workflow_success": False,
            "route_correct": False,
            "priority_correct": False,
            "stage_correct": False,
            "score_in_range": False,
            "crm_writeback_correct": False,
            "task_generation_correct": False,
            "required_task_hit_rate": 0.0,
        }

    actual_route = _infer_route(list(actual_result.get("workflow_log") or []))
    score = int(actual_result.get("lead_score", -1))
    minimum, maximum = expected["lead_score_range"]
    task_titles = _normalize_titles(actual_result.get("task_payload"))
    required_titles = [_normalize_text(value) for value in expected["required_task_titles"]]
    hits = 0
    for required_title in required_titles:
        if any(required_title in actual_title for actual_title in task_titles):
            hits += 1
    required_task_hit_rate = 1.0 if not required_titles else hits / len(required_titles)
    crm_written = bool(actual_result.get("crm_update_ids"))
    tasks_generated = bool(task_titles)

    return {
        "workflow_success": True,
        "route_correct": actual_route == expected["expected_route"],
        "priority_correct": _normalize_text(actual_result.get("lead_priority")) == _normalize_text(expected["lead_priority"]),
        "stage_correct": _normalize_text(actual_result.get("opportunity_stage")) == _normalize_text(expected["opportunity_stage"]),
        "score_in_range": minimum <= score <= maximum,
        "crm_writeback_correct": crm_written is bool(expected["should_write_crm"]),
        "task_generation_correct": tasks_generated is bool(expected["should_generate_tasks"]),
        "required_task_hit_rate": required_task_hit_rate,
    }


def summarize_workflow_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(rows) or 1
    return {
        "workflow_success_rate": sum(float(row["workflow_success"]) for row in rows) / count,
        "route_accuracy": sum(float(row["route_correct"]) for row in rows) / count,
        "priority_accuracy": sum(float(row["priority_correct"]) for row in rows) / count,
        "stage_accuracy": sum(float(row["stage_correct"]) for row in rows) / count,
        "score_range_accuracy": sum(float(row["score_in_range"]) for row in rows) / count,
        "crm_writeback_accuracy": sum(float(row["crm_writeback_correct"]) for row in rows) / count,
        "task_generation_hit_rate": sum(float(row["task_generation_correct"]) for row in rows) / count,
        "required_task_hit_rate": sum(float(row["required_task_hit_rate"]) for row in rows) / count,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest tests/evals/test_sales_copilot_metrics.py -q`

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add evals/sales_copilot/metrics.py tests/evals/test_sales_copilot_metrics.py
git commit -m "feat: add sales copilot workflow metrics"
```

### Task 4: Runner, Reporting, And CLI

**Files:**
- Create: `evals/sales_copilot/runner.py`
- Create: `evals/sales_copilot/reporting.py`
- Create: `scripts/run_sales_copilot_eval.py`
- Create: `tests/evals/test_sales_copilot_runner.py`

- [ ] **Step 1: Write the failing runner/reporting tests**

```python
import json
from pathlib import Path

from evals.sales_copilot.reporting import write_report_bundle
from evals.sales_copilot.runner import run_offline_evaluation


class FakeLLM:
    def complete(self, messages, response_format=None):
        prompt_text = "\n".join(message["content"] for message in messages)
        if "Parse the meeting notes" in prompt_text:
            return '{"account_name":"Acme Robotics","customer_roles":["CTO"],"confirmed_needs":["private deployment"],"budget_signals":["pilot approved"],"timeline_signals":["this quarter"],"next_steps":["schedule technical demo"],"competitors":[]}'
        if "Evaluate the lead" in prompt_text:
            return '{"lead_score":88,"lead_priority":"high","opportunity_stage":"proposal","risk_flags":[]}'
        if "follow-up plan" in prompt_text.lower():
            return '{"summary":"Schedule the technical demo","tasks":[{"title":"Schedule technical demo","priority":"high","due_at":"2026-04-10"}]}'
        raise AssertionError(prompt_text)


def test_run_offline_evaluation_returns_case_results_and_summary(tmp_path: Path):
    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(
        '{"case_id":"manufacturing_complete_001","segment":"high_intent_complete","customer_profile_text":"Account: Acme Robotics","meeting_note_text":"The CTO approved a private deployment pilot this quarter.","expected_parse":{"account_name":"Acme Robotics","customer_roles":["CTO"],"confirmed_needs":["private deployment"],"budget_signals":["pilot approved"],"timeline_signals":["this quarter"],"next_steps":["schedule technical demo"],"competitors":[]},"expected_workflow":{"lead_score_range":[80,95],"lead_priority":"high","opportunity_stage":"proposal","expected_route":"high_priority_follow_up","should_write_crm":true,"should_generate_tasks":true,"required_task_titles":["schedule technical demo"],"required_risk_flags":[]}}\\n',
        encoding="utf-8",
    )

    result = run_offline_evaluation(cases_path=cases_path, output_dir=tmp_path / "outputs", llm_client=FakeLLM())

    assert result["summary"]["parse"]["json_valid_rate"] == 1.0
    assert result["summary"]["workflow"]["workflow_success_rate"] == 1.0
    assert result["case_results"][0]["case_id"] == "manufacturing_complete_001"


def test_write_report_bundle_writes_json_markdown_and_jsonl(tmp_path: Path):
    bundle = {
        "summary": {"parse": {"json_valid_rate": 1.0}, "workflow": {"workflow_success_rate": 1.0}},
        "case_results": [{"case_id": "manufacturing_complete_001", "segment": "high_intent_complete"}],
    }

    report_dir = write_report_bundle(bundle, tmp_path)

    assert (report_dir / "report.json").exists()
    assert (report_dir / "report.md").exists()
    assert (report_dir / "case_results.jsonl").exists()
    assert "workflow_success_rate" in (report_dir / "report.md").read_text(encoding="utf-8")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest tests/evals/test_sales_copilot_runner.py -q`

Expected: FAIL with missing `run_offline_evaluation` or `write_report_bundle`

- [ ] **Step 3: Implement runner, per-case DB seeding, report writer, and CLI**

```python
# evals/sales_copilot/runner.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evals.sales_copilot.cases import load_golden_cases
from evals.sales_copilot.metrics import evaluate_parse_case, evaluate_workflow_case, summarize_parse_metrics, summarize_workflow_metrics
from sales_copilot.graph import parse_meeting_note_node
from sales_copilot.runner import run_sales_copilot
from sales_copilot.tools import seed_knowledge_chunks


DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "sales_copilot"


def _load_seed_rows(path: Path, source_type: str) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload if isinstance(payload, list) else payload.get("chunks", [])
    return [
        {
            "source_type": source_type,
            "source_name": row["source_name"],
            "chunk_text": row["chunk_text"],
            "tags": list(row.get("tags", [])),
            "retrieval_metadata": dict(row.get("retrieval_metadata", {})),
        }
        for row in rows
    ]


def _seed_eval_db(db_path: Path) -> None:
    seed_knowledge_chunks(db_path, _load_seed_rows(DATA_DIR / "seed_product_knowledge.json", "product"))
    seed_knowledge_chunks(db_path, _load_seed_rows(DATA_DIR / "seed_sales_playbook.json", "playbook"))


def run_offline_evaluation(*, cases_path: str | Path, output_dir: str | Path, llm_client) -> dict[str, Any]:
    cases = load_golden_cases(cases_path)
    output_root = Path(output_dir)
    db_root = output_root / "_case_dbs"
    db_root.mkdir(parents=True, exist_ok=True)

    case_results: list[dict[str, Any]] = []
    parse_rows: list[dict[str, Any]] = []
    workflow_rows: list[dict[str, Any]] = []

    for case in cases:
        db_path = db_root / f"{case['case_id']}.db"
        _seed_eval_db(db_path)

        parse_result = parse_meeting_note_node(
            {"customer_profile_raw": case["customer_profile_text"], "meeting_note_raw": case["meeting_note_text"], "workflow_log": []},
            llm_client=llm_client,
            database_path=db_path,
        )
        workflow_result = run_sales_copilot(
            customer_profile_text=case["customer_profile_text"],
            meeting_note_text=case["meeting_note_text"],
            database_path=db_path,
            llm_client=llm_client,
        )

        parse_metrics = evaluate_parse_case(case, parse_result.get("meeting_summary"))
        workflow_metrics = evaluate_workflow_case(case, workflow_result)
        parse_rows.append(parse_metrics)
        workflow_rows.append(workflow_metrics)
        case_results.append(
            {
                "case_id": case["case_id"],
                "segment": case["segment"],
                "parse_result": parse_result.get("meeting_summary"),
                "workflow_result": workflow_result,
                "parse_metrics": parse_metrics,
                "workflow_metrics": workflow_metrics,
            }
        )

    return {
        "summary": {
            "parse": summarize_parse_metrics(parse_rows),
            "workflow": summarize_workflow_metrics(workflow_rows),
        },
        "case_results": case_results,
    }
```

```python
# evals/sales_copilot/reporting.py
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def _render_markdown(summary: dict[str, Any]) -> str:
    parse = summary["parse"]
    workflow = summary["workflow"]
    return "\n".join(
        [
            "# Sales Copilot Offline Evaluation Report",
            "",
            "## Parse Metrics",
            f"- json_valid_rate: {parse['json_valid_rate']:.3f}",
            f"- average_list_field_f1: {parse['average_list_field_f1']:.3f}",
            "",
            "## Workflow Metrics",
            f"- workflow_success_rate: {workflow['workflow_success_rate']:.3f}",
            f"- route_accuracy: {workflow['route_accuracy']:.3f}",
            f"- required_task_hit_rate: {workflow['required_task_hit_rate']:.3f}",
        ]
    )


def write_report_bundle(bundle: dict[str, Any], output_root: str | Path) -> Path:
    report_dir = Path(output_root) / datetime.now().strftime("%Y%m%d-%H%M%S")
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "report.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    (report_dir / "report.md").write_text(_render_markdown(bundle["summary"]), encoding="utf-8")
    with (report_dir / "case_results.jsonl").open("w", encoding="utf-8") as handle:
        for row in bundle["case_results"]:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return report_dir
```

```python
# scripts/run_sales_copilot_eval.py
from __future__ import annotations

import argparse
import os
from pathlib import Path

from evals.sales_copilot.reporting import write_report_bundle
from evals.sales_copilot.runner import run_offline_evaluation
from llm.deepseek_client import DeepSeekClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Sales Copilot offline benchmark")
    parser.add_argument("--cases", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--mode", default="offline", choices=["offline"])
    parser.add_argument("--api-base-url", default="https://api.deepseek.com")
    parser.add_argument("--api-model", default="deepseek-chat")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    api_key = os.environ["DEEPSEEK_API_KEY"]
    client = DeepSeekClient(api_key=api_key, base_url=args.api_base_url, model=args.api_model)
    bundle = run_offline_evaluation(cases_path=Path(args.cases), output_dir=Path(args.output_dir), llm_client=client)
    report_dir = write_report_bundle(bundle, Path(args.output_dir))
    print(report_dir)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest tests/evals/test_sales_copilot_runner.py -q`

Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add evals/sales_copilot/runner.py evals/sales_copilot/reporting.py scripts/run_sales_copilot_eval.py tests/evals/test_sales_copilot_runner.py
git commit -m "feat: add sales copilot offline eval runner"
```

### Task 5: Expand The High-Intent Benchmark Cases

**Files:**
- Modify: `evals/sales_copilot/golden_cases.jsonl`

- [ ] **Step 1: Append three additional `high_intent_complete` cases**

```json
{"case_id":"manufacturing_complete_002","segment":"high_intent_complete","customer_profile_text":"Account: Acme Robotics\nIndustry: Manufacturing\nCurrent stage: Discovery","meeting_note_text":"The security lead approved the checklist, procurement confirmed pilot budget, and the team asked for the deployment workshop next week.","expected_parse":{"account_name":"Acme Robotics","customer_roles":["Security Lead","Procurement"],"confirmed_needs":["security checklist","deployment workshop"],"budget_signals":["pilot budget confirmed"],"timeline_signals":["next week"],"next_steps":["run deployment workshop"],"competitors":[]},"expected_workflow":{"lead_score_range":[80,95],"lead_priority":"high","opportunity_stage":"proposal","expected_route":"high_priority_follow_up","should_write_crm":true,"should_generate_tasks":true,"required_task_titles":["run deployment workshop"],"required_risk_flags":[]}}
{"case_id":"enterprise_complete_001","segment":"high_intent_complete","customer_profile_text":"Account: Northstar Logistics\nIndustry: Logistics\nCurrent stage: Qualification","meeting_note_text":"The VP of Operations confirmed budget ownership, requested a proposal this month, and asked for CRM integration details before procurement review.","expected_parse":{"account_name":"Northstar Logistics","customer_roles":["VP of Operations"],"confirmed_needs":["CRM integration","proposal"],"budget_signals":["budget owner confirmed"],"timeline_signals":["this month"],"next_steps":["send proposal"],"competitors":[]},"expected_workflow":{"lead_score_range":[78,92],"lead_priority":"high","opportunity_stage":"proposal","expected_route":"high_priority_follow_up","should_write_crm":true,"should_generate_tasks":true,"required_task_titles":["send proposal"],"required_risk_flags":[]}}
{"case_id":"saas_complete_001","segment":"high_intent_complete","customer_profile_text":"Account: Aurora SaaS\nIndustry: Software\nCurrent stage: Qualification","meeting_note_text":"The revenue operations lead approved a pilot timeline, confirmed a dedicated admin owner, and asked for the statement of work by Friday.","expected_parse":{"account_name":"Aurora SaaS","customer_roles":["Revenue Operations Lead"],"confirmed_needs":["pilot timeline","statement of work"],"budget_signals":["pilot approved"],"timeline_signals":["by friday"],"next_steps":["send statement of work"],"competitors":[]},"expected_workflow":{"lead_score_range":[78,90],"lead_priority":"high","opportunity_stage":"proposal","expected_route":"high_priority_follow_up","should_write_crm":true,"should_generate_tasks":true,"required_task_titles":["send statement of work"],"required_risk_flags":[]}}
```

- [ ] **Step 2: Append three `high_intent_missing_facts` cases**

```json
{"case_id":"healthcare_missing_002","segment":"high_intent_missing_facts","customer_profile_text":"Account: BluePeak Health\nIndustry: Healthcare\nCurrent stage: Qualification","meeting_note_text":"The compliance manager wants audit logging and CRM integration, but no budget owner or target decision date was confirmed.","expected_parse":{"account_name":"BluePeak Health","customer_roles":["Compliance Manager"],"confirmed_needs":["audit logging","CRM integration"],"budget_signals":[],"timeline_signals":[],"next_steps":[],"competitors":[]},"expected_workflow":{"lead_score_range":[65,80],"lead_priority":"high","opportunity_stage":"qualification","expected_route":"standard_follow_up","should_write_crm":true,"should_generate_tasks":true,"required_task_titles":["confirm budget range","confirm decision timeline"],"required_risk_flags":["missing_required_facts"]}}
{"case_id":"manufacturing_missing_001","segment":"high_intent_missing_facts","customer_profile_text":"Account: Delta Machines\nIndustry: Manufacturing\nCurrent stage: Discovery","meeting_note_text":"The CTO wants private deployment and role-based access control, but the team still needs to identify procurement and legal stakeholders.","expected_parse":{"account_name":"Delta Machines","customer_roles":["CTO"],"confirmed_needs":["private deployment","role-based access control"],"budget_signals":[],"timeline_signals":[],"next_steps":[],"competitors":[]},"expected_workflow":{"lead_score_range":[68,82],"lead_priority":"high","opportunity_stage":"qualification","expected_route":"standard_follow_up","should_write_crm":true,"should_generate_tasks":true,"required_task_titles":["identify decision makers","schedule qualification follow-up"],"required_risk_flags":["missing_required_facts"]}}
{"case_id":"retail_missing_001","segment":"high_intent_missing_facts","customer_profile_text":"Account: Harbor Retail Group\nIndustry: Retail\nCurrent stage: Discovery","meeting_note_text":"The sales operations lead wants account memory and follow-up automation, but budget and implementation timing are still unknown.","expected_parse":{"account_name":"Harbor Retail Group","customer_roles":["Sales Operations Lead"],"confirmed_needs":["account memory","follow-up automation"],"budget_signals":[],"timeline_signals":[],"next_steps":[],"competitors":[]},"expected_workflow":{"lead_score_range":[62,78],"lead_priority":"high","opportunity_stage":"qualification","expected_route":"standard_follow_up","should_write_crm":true,"should_generate_tasks":true,"required_task_titles":["confirm budget range","confirm decision timeline"],"required_risk_flags":["missing_required_facts"]}}
```

- [ ] **Step 3: Verify the loader still passes on the expanded dataset**

Run: `& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest tests/evals/test_sales_copilot_cases.py -q`

Expected: `2 passed`

- [ ] **Step 4: Commit**

```bash
git add evals/sales_copilot/golden_cases.jsonl
git commit -m "test: expand sales copilot high-intent benchmark cases"
```

### Task 6: Expand The Medium-Intent And Noise Benchmark Cases

**Files:**
- Modify: `evals/sales_copilot/golden_cases.jsonl`
- Modify: `tests/evals/test_sales_copilot_cases.py`

- [ ] **Step 1: Add three more `medium_intent_nurture` cases and three more `low_intent_or_noise` cases**

```json
{"case_id":"retail_nurture_002","segment":"medium_intent_nurture","customer_profile_text":"Account: Northwind Traders\nIndustry: Retail\nCurrent stage: Discovery","meeting_note_text":"The operations manager wants sample dashboards and a case study first. There is no project sponsor yet.","expected_parse":{"account_name":"Northwind Traders","customer_roles":["Operations Manager"],"confirmed_needs":["sample dashboards","case study"],"budget_signals":[],"timeline_signals":[],"next_steps":["send case study"],"competitors":[]},"expected_workflow":{"lead_score_range":[35,49],"lead_priority":"low","opportunity_stage":"discovery","expected_route":"low_priority_nurture","should_write_crm":true,"should_generate_tasks":false,"required_task_titles":[],"required_risk_flags":[]}}
{"case_id":"finance_nurture_001","segment":"medium_intent_nurture","customer_profile_text":"Account: Meridian Finance\nIndustry: Financial Services\nCurrent stage: Discovery","meeting_note_text":"The analytics manager likes the dashboard concept but asked to revisit after the quarter closes.","expected_parse":{"account_name":"Meridian Finance","customer_roles":["Analytics Manager"],"confirmed_needs":["dashboard concept"],"budget_signals":[],"timeline_signals":["after quarter close"],"next_steps":["revisit next quarter"],"competitors":[]},"expected_workflow":{"lead_score_range":[35,49],"lead_priority":"low","opportunity_stage":"discovery","expected_route":"low_priority_nurture","should_write_crm":true,"should_generate_tasks":false,"required_task_titles":[],"required_risk_flags":[]}}
{"case_id":"education_nurture_001","segment":"medium_intent_nurture","customer_profile_text":"Account: Summit Education\nIndustry: Education\nCurrent stage: Discovery","meeting_note_text":"The dean is curious about follow-up workflows, but the team only wants reference material for now.","expected_parse":{"account_name":"Summit Education","customer_roles":["Dean"],"confirmed_needs":["follow-up workflows"],"budget_signals":[],"timeline_signals":[],"next_steps":["send reference material"],"competitors":[]},"expected_workflow":{"lead_score_range":[35,49],"lead_priority":"low","opportunity_stage":"discovery","expected_route":"low_priority_nurture","should_write_crm":true,"should_generate_tasks":false,"required_task_titles":[],"required_risk_flags":[]}}
{"case_id":"noise_002","segment":"low_intent_or_noise","customer_profile_text":"Account: Orchard Foods\nIndustry: Food Processing\nCurrent stage: Discovery","meeting_note_text":"The contact requested a generic one-pager and said there is no active initiative this year.","expected_parse":{"account_name":"Orchard Foods","customer_roles":["Contact"],"confirmed_needs":["one-pager"],"budget_signals":[],"timeline_signals":[],"next_steps":["send one-pager"],"competitors":[]},"expected_workflow":{"lead_score_range":[0,35],"lead_priority":"low","opportunity_stage":"discovery","expected_route":"low_priority_nurture","should_write_crm":true,"should_generate_tasks":false,"required_task_titles":[],"required_risk_flags":[]}}
{"case_id":"noise_003","segment":"low_intent_or_noise","customer_profile_text":"Account: Atlas Print\nIndustry: Printing\nCurrent stage: Discovery","meeting_note_text":"The office manager only wanted pricing slides for internal awareness, with no sponsor or timeline.","expected_parse":{"account_name":"Atlas Print","customer_roles":["Office Manager"],"confirmed_needs":["pricing slides"],"budget_signals":[],"timeline_signals":[],"next_steps":["send pricing slides"],"competitors":[]},"expected_workflow":{"lead_score_range":[0,35],"lead_priority":"low","opportunity_stage":"discovery","expected_route":"low_priority_nurture","should_write_crm":true,"should_generate_tasks":false,"required_task_titles":[],"required_risk_flags":[]}}
{"case_id":"noise_004","segment":"low_intent_or_noise","customer_profile_text":"Account: Pineview Hotels\nIndustry: Hospitality\nCurrent stage: Discovery","meeting_note_text":"The buyer asked for a generic capability deck and said the team will revisit next year if priorities change.","expected_parse":{"account_name":"Pineview Hotels","customer_roles":["Buyer"],"confirmed_needs":["capability deck"],"budget_signals":[],"timeline_signals":["next year"],"next_steps":["send capability deck"],"competitors":[]},"expected_workflow":{"lead_score_range":[0,35],"lead_priority":"low","opportunity_stage":"discovery","expected_route":"low_priority_nurture","should_write_crm":true,"should_generate_tasks":false,"required_task_titles":[],"required_risk_flags":[]}}
```

- [ ] **Step 2: Add a dataset-integrity test for unique IDs and segment coverage**

```python
from pathlib import Path

from evals.sales_copilot.cases import load_golden_cases


def test_golden_case_file_has_unique_ids_and_balanced_segment_coverage():
    cases = load_golden_cases(Path("evals/sales_copilot/golden_cases.jsonl"))

    case_ids = [case["case_id"] for case in cases]
    segments = [case["segment"] for case in cases]

    assert len(cases) == 16
    assert len(case_ids) == len(set(case_ids))
    assert segments.count("high_intent_complete") == 4
    assert segments.count("high_intent_missing_facts") == 4
    assert segments.count("medium_intent_nurture") == 4
    assert segments.count("low_intent_or_noise") == 4
```

- [ ] **Step 3: Run the dataset test**

Run: `& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest tests/evals/test_sales_copilot_cases.py -q`

Expected: `3 passed`

- [ ] **Step 4: Commit**

```bash
git add evals/sales_copilot/golden_cases.jsonl tests/evals/test_sales_copilot_cases.py
git commit -m "test: complete sales copilot offline benchmark dataset"
```

### Task 7: Documentation, End-To-End Verification, And First Report

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add an evaluation section to the README**

````md
## Sales Copilot Offline Evaluation

Run the offline benchmark against the local golden dataset:

```powershell
$env:DEEPSEEK_API_KEY="your-key"
& 'D:\anaconda\envs\minimind_job_agent\python.exe' `
  D:\minimind\.worktrees\minimind-job-agent\scripts\run_sales_copilot_eval.py `
  --cases D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\golden_cases.jsonl `
  --output-dir D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs `
  --mode offline
```

The command writes:

- `report.json`
- `report.md`
- `case_results.jsonl`

Use the generated metrics for regression tracking and resume-safe project writeups.
````

- [ ] **Step 2: Run the full evaluation test suite**

Run: `& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest tests/evals tests/sales_copilot tests/llm/test_deepseek_client.py tests/scripts/test_sales_copilot_web_utils.py -q`

Expected: PASS for all evaluation tests and the existing `Sales Copilot` regression suite

- [ ] **Step 3: If `DEEPSEEK_API_KEY` is available, generate the first benchmark report**

Run:

```powershell
$env:DEEPSEEK_API_KEY="your-key"
& 'D:\anaconda\envs\minimind_job_agent\python.exe' `
  D:\minimind\.worktrees\minimind-job-agent\scripts\run_sales_copilot_eval.py `
  --cases D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\golden_cases.jsonl `
  --output-dir D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs `
  --mode offline
```

Expected:

- a new timestamped directory under `evals/sales_copilot/outputs/`
- `report.json`, `report.md`, and `case_results.jsonl` exist
- `report.md` contains `workflow_success_rate`, `route_accuracy`, and `average_list_field_f1`

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: add sales copilot offline evaluation guide"
```
