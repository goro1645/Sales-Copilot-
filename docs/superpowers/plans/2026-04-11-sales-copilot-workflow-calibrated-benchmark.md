# Sales Copilot Workflow-Calibrated Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a 30-case AI-calibrated workflow benchmark draft that evaluates CRM writeback and task generation quality using realistic CSDS-derived source cases.

**Architecture:** Add a focused workflow benchmark builder that reuses the existing AI-calibrated 100 parse benchmark as the source pool, selects a route-balanced 30-case subset, asks DeepSeek to produce rich workflow expectations for each case, and exports both a final JSONL benchmark and a Markdown field guide. Keep current parse benchmark logic untouched and isolate the new behavior in a dedicated module and CLI.

**Tech Stack:** Python, JSONL, DeepSeek tool-calls, pytest

---

### Task 1: Add failing tests for workflow benchmark selection and export

**Files:**
- Create: `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_workflow_calibrated_benchmark.py`

- [ ] **Step 1: Write the failing tests**

```python
from __future__ import annotations

from evals.sales_copilot.workflow_calibrated_benchmark import (
    build_workflow_calibrated_sample,
    export_final_workflow_calibrated_rows,
    infer_workflow_sampling_bucket,
)


def _build_row(case_id: str, *, expected_parse: dict[str, object], meeting_note_text: str = "m") -> dict[str, object]:
    return {
        "case_id": case_id,
        "source_dataset": "full-csds-ai-calibrated",
        "meeting_note_text": meeting_note_text,
        "customer_profile_text": "Source: CSDS",
        "expected_parse": expected_parse,
    }


def test_infer_workflow_sampling_bucket_identifies_need_more_info() -> None:
    row = _build_row(
        "case_need_info",
        expected_parse={
            "account_name": "JD Support",
            "customer_roles": ["user", "agent"],
            "confirmed_needs": ["integration support"],
            "budget_signals": [],
            "timeline_signals": [],
            "next_steps": [],
            "competitors": [],
        },
        meeting_note_text="Customer is interested but budget and timeline are still unclear.",
    )

    assert infer_workflow_sampling_bucket(row) == "need_more_info"


def test_build_workflow_calibrated_sample_hits_route_targets() -> None:
    rows = []
    for index in range(10):
        rows.append(
            _build_row(
                f"high_{index}",
                expected_parse={
                    "account_name": "A",
                    "customer_roles": [],
                    "confirmed_needs": ["proposal"],
                    "budget_signals": ["budget confirmed"],
                    "timeline_signals": ["next week"],
                    "next_steps": ["send proposal"],
                    "competitors": [],
                },
                meeting_note_text="Budget confirmed and proposal needed next week.",
            )
        )
    for index in range(10):
        rows.append(
            _build_row(
                f"standard_{index}",
                expected_parse={
                    "account_name": "B",
                    "customer_roles": [],
                    "confirmed_needs": ["solution details"],
                    "budget_signals": [],
                    "timeline_signals": [],
                    "next_steps": ["follow up with details"],
                    "competitors": [],
                },
                meeting_note_text="Needs follow-up with solution details.",
            )
        )
    for index in range(10):
        rows.append(
            _build_row(
                f"nurture_{index}",
                expected_parse={
                    "account_name": "C",
                    "customer_roles": [],
                    "confirmed_needs": ["reference material"],
                    "budget_signals": [],
                    "timeline_signals": [],
                    "next_steps": ["send reference material"],
                    "competitors": [],
                },
                meeting_note_text="Send reference material and revisit next year.",
            )
        )
    for index in range(10):
        rows.append(
            _build_row(
                f"need_{index}",
                expected_parse={
                    "account_name": "D",
                    "customer_roles": [],
                    "confirmed_needs": ["crm integration"],
                    "budget_signals": [],
                    "timeline_signals": [],
                    "next_steps": [],
                    "competitors": [],
                },
                meeting_note_text="Interested but budget and timeline are not confirmed yet.",
            )
        )

    sample = build_workflow_calibrated_sample(rows)

    bucket_counts: dict[str, int] = {}
    for row in sample:
        bucket = str(row["workflow_sampling_bucket"])
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1

    assert len(sample) == 30
    assert bucket_counts["high_priority_follow_up"] == 8
    assert bucket_counts["standard_follow_up"] == 8
    assert bucket_counts["low_priority_nurture"] == 7
    assert bucket_counts["need_more_info"] == 7


def test_export_final_workflow_calibrated_rows_builds_compatibility_fields() -> None:
    rows = [
        {
            "case_id": "case_1",
            "segment": "workflow_calibrated_subset",
            "source_dataset": "full-csds-ai-calibrated",
            "meeting_note_text": "m",
            "customer_profile_text": "c",
            "expected_parse": {
                "account_name": "JD Support",
                "customer_roles": ["user", "agent"],
                "confirmed_needs": ["proposal"],
                "budget_signals": ["budget confirmed"],
                "timeline_signals": ["next week"],
                "next_steps": ["send proposal"],
                "competitors": [],
            },
            "workflow_review": {
                "expected_workflow": {
                    "lead_score_range": [80, 90],
                    "lead_priority": "high",
                    "opportunity_stage": "proposal",
                    "expected_route": "high_priority_follow_up",
                    "expected_crm_writeback": {
                        "should_write": True,
                        "account_status": "active",
                        "opportunity_stage": "proposal",
                        "risk_flags": ["approved_budget"],
                        "recommended_next_step": "send proposal",
                        "evidence": ["budget confirmed"],
                        "acceptable_variants": ["share proposal"],
                    },
                    "expected_task_bundle": {
                        "should_generate": True,
                        "tasks": [
                            {
                                "title": "send proposal",
                                "description": "Send a formal proposal.",
                                "priority": "high",
                                "owner": "Sales",
                                "timing_expectation": "next_day",
                                "evidence": ["proposal requested"],
                            }
                        ],
                        "acceptable_variants": ["share proposal deck"],
                    },
                },
                "calibration_note": "AI draft",
            },
        }
    ]

    final_rows = export_final_workflow_calibrated_rows(rows)
    workflow = final_rows[0]["expected_workflow"]

    assert workflow["should_write_crm"] is True
    assert workflow["should_generate_tasks"] is True
    assert workflow["required_task_titles"] == ["send proposal"]
    assert workflow["required_risk_flags"] == ["approved_budget"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_workflow_calibrated_benchmark.py -q`
Expected: FAIL with import errors because the workflow benchmark module does not exist yet.

- [ ] **Step 3: Commit the red test**

```bash
git -C D:\minimind\.worktrees\minimind-job-agent add -- tests/evals/test_workflow_calibrated_benchmark.py
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "test: add workflow benchmark selection coverage"
```

### Task 2: Implement workflow benchmark selection and AI review helpers

**Files:**
- Create: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\workflow_calibrated_benchmark.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_workflow_calibrated_benchmark.py`

- [ ] **Step 1: Write the minimal implementation**

```python
from __future__ import annotations

from typing import Any


WORKFLOW_TARGET_BUCKETS = {
    "high_priority_follow_up": 8,
    "standard_follow_up": 8,
    "low_priority_nurture": 7,
    "need_more_info": 7,
}


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _normalize_text(value: Any) -> str:
    return str(value or "").strip().lower()


def infer_workflow_sampling_bucket(row: dict[str, object]) -> str:
    expected_parse = row.get("expected_parse", {})
    if not isinstance(expected_parse, dict):
        expected_parse = {}
    meeting_note_text = _normalize_text(row.get("meeting_note_text"))
    budget = _normalize_string_list(expected_parse.get("budget_signals", []))
    timeline = _normalize_string_list(expected_parse.get("timeline_signals", []))
    next_steps = _normalize_string_list(expected_parse.get("next_steps", []))

    if not next_steps or any(marker in meeting_note_text for marker in ("unclear", "not confirmed", "缺", "未确认", "没有")):
        return "need_more_info"
    if budget or timeline or any(marker in meeting_note_text for marker in ("next week", "this week", "approved", "本周", "下周", "尽快")):
        return "high_priority_follow_up"
    if any(marker in meeting_note_text for marker in ("next year", "later", "reference", "material", "以后", "参考", "资料")):
        return "low_priority_nurture"
    return "standard_follow_up"


def build_workflow_calibrated_sample(
    rows: list[dict[str, object]],
    *,
    target_counts: dict[str, int] | None = None,
) -> list[dict[str, object]]:
    targets = dict(target_counts or WORKFLOW_TARGET_BUCKETS)
    grouped = {bucket: [] for bucket in targets}
    for row in rows:
        bucket = infer_workflow_sampling_bucket(row)
        if bucket in grouped:
            grouped[bucket].append(dict(row))

    selected: list[dict[str, object]] = []
    seen: set[str] = set()
    for bucket, count in targets.items():
        for row in grouped[bucket]:
            case_id = str(row.get("case_id", ""))
            if case_id in seen:
                continue
            row["workflow_sampling_bucket"] = bucket
            selected.append(row)
            seen.add(case_id)
            if sum(1 for item in selected if item["workflow_sampling_bucket"] == bucket) >= count:
                break
    return selected


def export_final_workflow_calibrated_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    final_rows: list[dict[str, Any]] = []
    for row in rows:
        review = row.get("workflow_review", {})
        workflow = dict(review.get("expected_workflow", {})) if isinstance(review, dict) else {}
        crm = dict(workflow.get("expected_crm_writeback", {}))
        task_bundle = dict(workflow.get("expected_task_bundle", {}))
        tasks = task_bundle.get("tasks", [])
        titles = [task.get("title", "").strip() for task in tasks if isinstance(task, dict) and str(task.get("title", "")).strip()]

        workflow["should_write_crm"] = bool(crm.get("should_write", False))
        workflow["should_generate_tasks"] = bool(task_bundle.get("should_generate", False))
        workflow["required_task_titles"] = titles
        workflow["required_risk_flags"] = _normalize_string_list(crm.get("risk_flags", []))

        final_rows.append(
            {
                "case_id": row.get("case_id", ""),
                "segment": row.get("segment", "workflow_calibrated_subset"),
                "source_dataset": row.get("source_dataset", "full-csds-ai-calibrated"),
                "meeting_note_text": row.get("meeting_note_text", ""),
                "customer_profile_text": row.get("customer_profile_text", ""),
                "expected_parse": row.get("expected_parse", {}),
                "expected_workflow": workflow,
                "calibration_note": review.get("calibration_note", ""),
            }
        )
    return final_rows
```

- [ ] **Step 2: Run the focused tests**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_workflow_calibrated_benchmark.py -q`
Expected: PASS

- [ ] **Step 3: Add AI workflow review helpers**

```python
WORKFLOW_REVIEW_TOOL_NAME = "submit_ai_calibrated_workflow"


def build_workflow_review_tools() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": WORKFLOW_REVIEW_TOOL_NAME,
                "description": "Return the final AI-calibrated workflow expectation for a Sales Copilot case.",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "expected_workflow": {
                            "type": "object",
                            "properties": {
                                "lead_score_range": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
                                "lead_priority": {"type": "string", "enum": ["low", "medium", "high"]},
                                "opportunity_stage": {"type": "string", "enum": ["discovery", "qualification", "proposal", "negotiation", "closed_won", "closed_lost"]},
                                "expected_route": {"type": "string", "enum": ["need_more_info", "low_priority_nurture", "standard_follow_up", "high_priority_follow_up"]},
                                "expected_crm_writeback": {"type": "object"},
                                "expected_task_bundle": {"type": "object"},
                            },
                            "required": ["lead_score_range", "lead_priority", "opportunity_stage", "expected_route", "expected_crm_writeback", "expected_task_bundle"],
                            "additionalProperties": False,
                        },
                        "calibration_note": {"type": "string"},
                    },
                    "required": ["expected_workflow", "calibration_note"],
                    "additionalProperties": False,
                },
            },
        }
    ]
```

- [ ] **Step 4: Run tests again**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_workflow_calibrated_benchmark.py -q`
Expected: PASS with helper additions integrated cleanly.

- [ ] **Step 5: Commit**

```bash
git -C D:\minimind\.worktrees\minimind-job-agent add -- evals/sales_copilot/workflow_calibrated_benchmark.py tests/evals/test_workflow_calibrated_benchmark.py
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "feat: add workflow calibrated benchmark helpers"
```

### Task 3: Add CLI and end-to-end export coverage

**Files:**
- Create: `D:\minimind\.worktrees\minimind-job-agent\scripts\build_workflow_calibrated_benchmark.py`
- Create: `D:\minimind\.worktrees\minimind-job-agent\tests\scripts\test_build_workflow_calibrated_benchmark.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\workflow_calibrated_benchmark.py`

- [ ] **Step 1: Write the failing CLI test**

```python
from __future__ import annotations

from pathlib import Path

from scripts import build_workflow_calibrated_benchmark


def test_build_workflow_calibrated_benchmark_cli_writes_final_files(monkeypatch, tmp_path: Path) -> None:
    source_path = tmp_path / "source.jsonl"
    source_path.write_text(
        (
            '{"case_id":"case_1","source_dataset":"full-csds-ai-calibrated","meeting_note_text":"Budget confirmed and proposal needed next week.",'
            '"customer_profile_text":"Source: CSDS","expected_parse":{"account_name":"A","customer_roles":[],"confirmed_needs":["proposal"],'
            '"budget_signals":["budget confirmed"],"timeline_signals":["next week"],"next_steps":["send proposal"],"competitors":[]}}\n'
        ),
        encoding="utf-8",
    )

    class _FakeClient:
        def complete_with_tool(self, messages, tools, tool_choice):
            return {
                "tool_name": "submit_ai_calibrated_workflow",
                "arguments": {
                    "expected_workflow": {
                        "lead_score_range": [80, 90],
                        "lead_priority": "high",
                        "opportunity_stage": "proposal",
                        "expected_route": "high_priority_follow_up",
                        "expected_crm_writeback": {
                            "should_write": True,
                            "account_status": "active",
                            "opportunity_stage": "proposal",
                            "risk_flags": ["approved_budget"],
                            "recommended_next_step": "send proposal",
                            "evidence": ["budget confirmed"],
                            "acceptable_variants": [],
                        },
                        "expected_task_bundle": {
                            "should_generate": True,
                            "tasks": [
                                {
                                    "title": "send proposal",
                                    "description": "Send proposal",
                                    "priority": "high",
                                    "owner": "Sales",
                                    "timing_expectation": "next_day",
                                    "evidence": ["proposal requested"],
                                }
                            ],
                            "acceptable_variants": [],
                        },
                    },
                    "calibration_note": "AI draft",
                },
            }

    monkeypatch.setattr(build_workflow_calibrated_benchmark, "_build_deepseek_client", lambda api_key, base_url, model: _FakeClient())
    monkeypatch.setattr(
        "sys.argv",
        [
            "build_workflow_calibrated_benchmark.py",
            "--source-jsonl",
            str(source_path),
            "--api-key",
            "test-key",
            "--output-dir",
            str(tmp_path / "outputs"),
        ],
    )

    assert build_workflow_calibrated_benchmark.main() == 0
    assert (tmp_path / "outputs" / "full_csds_workflow_calibrated_30.jsonl").exists()
    assert (tmp_path / "outputs" / "full_csds_workflow_calibrated_30_README.md").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\scripts\test_build_workflow_calibrated_benchmark.py -q`
Expected: FAIL because the CLI script does not exist yet.

- [ ] **Step 3: Implement the CLI**

```python
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evals.sales_copilot.workflow_calibrated_benchmark import (
    build_workflow_calibrated_sample,
    export_final_workflow_calibrated_rows,
    fill_ai_workflow_review_rows,
    load_jsonl_rows,
    write_jsonl,
    write_workflow_readme,
)
from llm.deepseek_client import DeepSeekClient


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a workflow-calibrated Sales Copilot benchmark draft.")
    parser.add_argument("--source-jsonl", default=str(REPO_ROOT / "evals" / "sales_copilot" / "outputs_csds_calibrated_100" / "full_csds_ai_calibrated_100.jsonl"))
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--api-key", default="")
    parser.add_argument("--api-base-url", default="https://api.deepseek.com")
    parser.add_argument("--api-model", default="deepseek-chat")
    return parser


def _build_deepseek_client(api_key: str, base_url: str, model: str):
    return DeepSeekClient(api_key=api_key, base_url=base_url, model=model)


def main() -> int:
    args = _build_parser().parse_args()
    api_key = str(args.api_key or os.environ.get("DEEPSEEK_API_KEY", "")).strip()
    if not api_key:
        raise SystemExit("Missing DeepSeek API key. Pass --api-key or set DEEPSEEK_API_KEY.")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = load_jsonl_rows(Path(args.source_jsonl))
    sampled = build_workflow_calibrated_sample(rows)
    client = _build_deepseek_client(api_key, args.api_base_url, args.api_model)
    reviewed = fill_ai_workflow_review_rows(sampled, llm_client=client)
    final_rows = export_final_workflow_calibrated_rows(reviewed)

    final_path = output_dir / "full_csds_workflow_calibrated_30.jsonl"
    readme_path = output_dir / "full_csds_workflow_calibrated_30_README.md"
    write_jsonl(final_path, final_rows)
    write_workflow_readme(readme_path, final_rows)

    print(f"Built {len(final_rows)} workflow-calibrated rows.")
    print(f"final_jsonl: {final_path}")
    print(f"readme_md: {readme_path}")
    return 0
```

- [ ] **Step 4: Run focused CLI tests**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\scripts\test_build_workflow_calibrated_benchmark.py -q`
Expected: PASS

- [ ] **Step 5: Run eval tests together**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_workflow_calibrated_benchmark.py D:\minimind\.worktrees\minimind-job-agent\tests\scripts\test_build_workflow_calibrated_benchmark.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git -C D:\minimind\.worktrees\minimind-job-agent add -- scripts/build_workflow_calibrated_benchmark.py tests/scripts/test_build_workflow_calibrated_benchmark.py evals/sales_copilot/workflow_calibrated_benchmark.py
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "feat: add workflow calibrated benchmark builder"
```

### Task 4: Generate the live workflow-calibrated 30 benchmark draft

**Files:**
- Create: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_workflow_calibrated_30\full_csds_workflow_calibrated_30.jsonl`
- Create: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_workflow_calibrated_30\full_csds_workflow_calibrated_30_README.md`

- [ ] **Step 1: Run the builder against the real AI-calibrated 100 pool**

Run:

```bash
set DEEPSEEK_API_KEY=...
D:\anaconda\envs\minimind_job_agent\python.exe D:\minimind\.worktrees\minimind-job-agent\scripts\build_workflow_calibrated_benchmark.py ^
  --source-jsonl D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_csds_calibrated_100\full_csds_ai_calibrated_100.jsonl ^
  --output-dir D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_workflow_calibrated_30
```

Expected:
- a final JSONL with 30 rows
- a Markdown field guide
- route-balanced coverage close to target counts

- [ ] **Step 2: Sanity-check the output structure**

Run:

```bash
D:\anaconda\envs\minimind_job_agent\python.exe - <<'PY'
from pathlib import Path
import json

path = Path(r"D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_workflow_calibrated_30\full_csds_workflow_calibrated_30.jsonl")
rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
assert len(rows) == 30
assert all("expected_workflow" in row for row in rows)
assert all("expected_crm_writeback" in row["expected_workflow"] for row in rows)
assert all("expected_task_bundle" in row["expected_workflow"] for row in rows)
print("rows:", len(rows))
print("routes:", {row["expected_workflow"]["expected_route"] for row in rows})
PY
```

Expected: output confirms 30 rows and all required workflow structures are present.

- [ ] **Step 3: Commit code only, not generated outputs**

```bash
git -C D:\minimind\.worktrees\minimind-job-agent add -- docs/superpowers/plans/2026-04-11-sales-copilot-workflow-calibrated-benchmark.md evals/sales_copilot/workflow_calibrated_benchmark.py scripts/build_workflow_calibrated_benchmark.py tests/evals/test_workflow_calibrated_benchmark.py tests/scripts/test_build_workflow_calibrated_benchmark.py
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "feat: add workflow calibrated benchmark pipeline"
```

## Self-Review

- Spec coverage: selection, full workflow expectation schema, final JSONL export, and Markdown guide are all covered by Tasks 1-4.
- Placeholder scan: no `TODO`/`TBD` placeholders remain in the executable steps.
- Type consistency: the final benchmark always uses `expected_workflow.expected_crm_writeback` and `expected_workflow.expected_task_bundle`, while compatibility fields are derived at export time.
