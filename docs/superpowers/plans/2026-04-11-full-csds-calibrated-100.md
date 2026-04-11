# Full-CSDS Calibrated-100 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible `100`-case calibrated working set from `full-csds test`, seed it with AI-assisted pre-annotation from existing baseline parse outputs, and support exporting a final calibrated benchmark file after human review.

**Architecture:** Reuse `load_full_csds_cases()` as the canonical weak-gold case loader, then layer a new `calibrated_subset.py` module on top for review-oriented bucketing, deterministic sampling, baseline-conflict detection from existing `case_results.jsonl`, pre-annotation generation, and working/final JSONL export. Keep this pipeline separate from the main parse runner so we can create a higher-trust benchmark without perturbing the existing `full-csds 800` weak benchmark.

**Tech Stack:** Python, existing CSDS adapter and metrics helpers, pytest, JSONL/JSON output

---

### Task 1: Add failing tests for calibrated sampling and pre-annotation

**Files:**
- Create: `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_calibrated_subset.py`

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

from evals.sales_copilot.calibrated_subset import (
    build_calibrated_working_rows,
    build_calibrated_sample,
)


def _build_case(
    case_id: str,
    *,
    meeting_note_text: str = "用户咨询订单处理进度，客服说明会在明天回复，并表示优惠券无法补用。",
    user_summ: list[str] | None = None,
    agent_summ: list[str] | None = None,
    final_summ: list[str] | None = None,
    expected_parse: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "source_uid": case_id.removeprefix("case_"),
        "source_split": "test",
        "source_note": "full-csds sample",
        "meeting_note_text": meeting_note_text,
        "customer_profile_text": "来源：CSDS",
        "expected_parse": expected_parse
        or {
            "account_name": "京东客服",
            "customer_roles": ["用户", "客服"],
            "confirmed_needs": ["咨询订单处理进度"],
            "budget_signals": [],
            "timeline_signals": [],
            "next_steps": ["客服后续回复用户"],
            "competitors": [],
        },
        "_raw_row": {
            "UserSumm": user_summ or ["用户咨询订单处理进度"],
            "AgentSumm": agent_summ or ["客服说明会在明天回复，并表示优惠券无法补用。"],
            "FinalSumm": final_summ or ["客服说明会在明天回复，并表示优惠券无法补用。"],
        },
    }


def test_build_calibrated_sample_hits_requested_bucket_sizes_with_backfill():
    cases = []
    for index in range(40):
        cases.append(_build_case(f"case_ord_{index}"))
    for index in range(25):
        cases.append(
            _build_case(
                f"case_time_{index}",
                meeting_note_text="客服表示明天联系用户，并在一个工作日内处理。",
                agent_summ=["客服表示明天联系用户，并在一个工作日内处理。"],
            )
        )
    for index in range(10):
        cases.append(
            _build_case(
                f"case_budget_{index}",
                meeting_note_text="客服表示优惠券无法补用，可申请退款。",
                agent_summ=["客服表示优惠券无法补用，可申请退款。"],
            )
        )
    for index in range(25):
        cases.append(
            _build_case(
                f"case_overlap_{index}",
                expected_parse={
                    "account_name": "京东客服",
                    "customer_roles": ["用户", "客服"],
                    "confirmed_needs": ["处理订单问题"],
                    "budget_signals": ["优惠券无法补用"],
                    "timeline_signals": ["明天回复用户"],
                    "next_steps": ["明天回复用户", "优惠券无法补用"],
                    "competitors": [],
                },
                agent_summ=["客服说明明天回复用户，优惠券无法补用。"],
            )
        )

    baseline_case_results = {
        "case_ord_0": {"parse_result": {"next_steps": ["客服会尽快回复用户"]}},
        "case_overlap_0": {"parse_result": {"budget_signals": ["可申请退款"], "next_steps": ["申请退款"]}},
    }

    rows = build_calibrated_sample(
        cases,
        baseline_case_results=baseline_case_results,
        target_counts={
            "ordinary_stable": 25,
            "timeline_boundary": 20,
            "budget_boundary": 20,
            "field_overlap_high_risk": 20,
            "model_rule_conflict": 15,
        },
    )

    bucket_counts: dict[str, int] = {}
    for row in rows:
        bucket = str(row["sampling_bucket"])
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1

    assert len(rows) == 100
    assert bucket_counts["ordinary_stable"] == 25
    assert bucket_counts["timeline_boundary"] == 20
    assert bucket_counts["budget_boundary"] == 20
    assert bucket_counts["field_overlap_high_risk"] == 20
    assert bucket_counts["model_rule_conflict"] == 15


def test_build_calibrated_working_rows_seeds_pre_annotation_from_baseline():
    case = _build_case(
        "case_conflict",
        expected_parse={
            "account_name": "京东客服",
            "customer_roles": ["用户", "客服"],
            "confirmed_needs": ["修改订单信息"],
            "budget_signals": [],
            "timeline_signals": [],
            "next_steps": ["客服后续回复用户"],
            "competitors": [],
        },
    )

    rows = build_calibrated_working_rows(
        [case],
        baseline_case_results={
            "case_conflict": {
                "parse_result": {
                    "account_name": "京东客服",
                    "customer_roles": ["用户", "客服"],
                    "confirmed_needs": ["修改订单信息"],
                    "budget_signals": ["优惠券无法补用"],
                    "timeline_signals": ["明天回复"],
                    "next_steps": ["申请修改订单信息"],
                    "competitors": [],
                }
            }
        },
    )

    row = rows[0]
    assert row["baseline_parse_result"]["budget_signals"] == ["优惠券无法补用"]
    assert row["pre_annotation"]["budget_signals_decision"] == "edit"
    assert row["pre_annotation"]["needs_human_review"] is True
    assert row["human_review"] == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_calibrated_subset.py -q`
Expected: FAIL with missing-module or missing-function errors for `evals.sales_copilot.calibrated_subset`.

- [ ] **Step 3: Commit**

```bash
git -C D:\minimind\.worktrees\minimind-job-agent add tests/evals/test_calibrated_subset.py
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "test: cover calibrated full-csds subset generation"
```

### Task 2: Implement calibrated subset helpers and final-export logic

**Files:**
- Create: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\calibrated_subset.py`
- Test: `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_calibrated_subset.py`

- [ ] **Step 1: Write minimal implementation**

```python
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from evals.sales_copilot.metrics import _set_precision_recall_f1


TARGET_BUCKETS = {
    "ordinary_stable": 25,
    "timeline_boundary": 20,
    "budget_boundary": 20,
    "field_overlap_high_risk": 20,
    "model_rule_conflict": 15,
}


def load_case_results_by_id(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            if isinstance(payload, dict) and isinstance(payload.get("case_id"), str):
                rows[payload["case_id"]] = payload
    return rows


def build_calibrated_sample(
    cases: list[dict[str, object]],
    *,
    baseline_case_results: dict[str, dict[str, Any]],
    target_counts: dict[str, int] | None = None,
) -> list[dict[str, object]]:
    ...


def build_calibrated_working_rows(
    cases: list[dict[str, object]],
    *,
    baseline_case_results: dict[str, dict[str, Any]],
) -> list[dict[str, object]]:
    ...


def export_final_calibrated_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ...
```

Implementation requirements:
- detect `budget_boundary` from raw summary text or `meeting_note_text`, not only from auto-gold
- detect `model_rule_conflict` from existing `case_results.jsonl` parse outputs
- deterministically sample rows and backfill sparse buckets using the fallback order from the spec
- include `_raw_row`-style source context in working rows when present
- seed `pre_annotation.corrected_expected_parse` with baseline parse values for the four review fields
- keep `human_review` empty (`{}`) in the generated working file
- export final rows by preferring `human_review.final_expected_parse` when present, otherwise falling back to `pre_annotation.corrected_expected_parse` for the review fields and original `expected_parse` for untouched fields

- [ ] **Step 2: Run targeted tests**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_calibrated_subset.py -q`
Expected: PASS

- [ ] **Step 3: Extend coverage for export behavior**

```python
def test_export_final_calibrated_rows_prefers_human_review_when_present():
    rows = [
        {
            "case_id": "case_1",
            "meeting_note_text": "客服说明明天联系用户。",
            "expected_parse": {
                "account_name": "京东客服",
                "customer_roles": ["用户", "客服"],
                "confirmed_needs": ["处理订单问题"],
                "budget_signals": [],
                "timeline_signals": [],
                "next_steps": ["客服后续回复用户"],
                "competitors": [],
            },
            "pre_annotation": {
                "corrected_expected_parse": {
                    "confirmed_needs": ["处理订单问题"],
                    "budget_signals": [],
                    "timeline_signals": ["明天联系用户"],
                    "next_steps": ["联系用户"],
                }
            },
            "human_review": {
                "final_expected_parse": {
                    "confirmed_needs": ["处理订单问题"],
                    "budget_signals": [],
                    "timeline_signals": ["明天联系用户"],
                    "next_steps": ["联系客服处理"],
                }
            },
        }
    ]

    final_rows = export_final_calibrated_rows(rows)

    assert final_rows[0]["expected_parse"]["next_steps"] == ["联系客服处理"]
```

- [ ] **Step 4: Re-run tests**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_calibrated_subset.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C D:\minimind\.worktrees\minimind-job-agent add evals/sales_copilot/calibrated_subset.py tests/evals/test_calibrated_subset.py
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "feat: add calibrated full-csds subset helpers"
```

### Task 3: Add CLI entrypoint and documentation

**Files:**
- Create: `D:\minimind\.worktrees\minimind-job-agent\scripts\build_full_csds_calibrated_subset.py`
- Create: `D:\minimind\.worktrees\minimind-job-agent\tests\scripts\test_build_full_csds_calibrated_subset.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\README.md`

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

from pathlib import Path

from scripts import build_full_csds_calibrated_subset


def test_build_full_csds_calibrated_subset_cli_writes_working_file(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "sys.argv",
        [
            "build_full_csds_calibrated_subset.py",
            "--csds-data-dir",
            str(tmp_path / "csds"),
            "--split",
            "test",
            "--baseline-case-results",
            str(tmp_path / "case_results.jsonl"),
            "--output-dir",
            str(tmp_path / "outputs"),
        ],
    )
    monkeypatch.setattr(
        build_full_csds_calibrated_subset,
        "load_full_csds_cases",
        lambda dataset_dir, splits=None, limit=None: [
            {
                "case_id": "case_1",
                "source_uid": "1",
                "source_split": "test",
                "source_note": "sample",
                "customer_profile_text": "来源：CSDS",
                "meeting_note_text": "客服说明明天联系用户。",
                "expected_parse": {
                    "account_name": "京东客服",
                    "customer_roles": ["用户", "客服"],
                    "confirmed_needs": ["处理订单问题"],
                    "budget_signals": [],
                    "timeline_signals": [],
                    "next_steps": ["客服后续回复用户"],
                    "competitors": [],
                },
            }
        ],
    )
    monkeypatch.setattr(
        build_full_csds_calibrated_subset,
        "_load_raw_split_rows",
        lambda dataset_dir, split: {"1": {"UserSumm": [], "AgentSumm": [], "FinalSumm": []}},
    )
    monkeypatch.setattr(
        build_full_csds_calibrated_subset,
        "load_case_results_by_id",
        lambda path: {},
    )

    assert build_full_csds_calibrated_subset.main() == 0
    assert (tmp_path / "outputs" / "full_csds_calibration_working_100.jsonl").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\scripts\test_build_full_csds_calibrated_subset.py -q`
Expected: FAIL with missing script/module errors.

- [ ] **Step 3: Implement minimal CLI**

```python
def main() -> int:
    ...
```

CLI behavior:
- load `full-csds` cases for the requested split
- load raw split rows so the working file preserves `UserSumm`, `AgentSumm`, `FinalSumm`
- load baseline parse outputs from an existing `case_results.jsonl`
- write:
  - `full_csds_calibration_working_100.jsonl`
- optionally accept `--export-final-from-working` to convert a reviewed working file into:
  - `full_csds_calibrated_100.jsonl`

Use this real baseline report path for documentation/examples:

`D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_csds_full_post_cache_move\20260410020844\case_results.jsonl`

- [ ] **Step 4: Re-run tests**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\scripts\test_build_full_csds_calibrated_subset.py -q`
Expected: PASS

- [ ] **Step 5: Update README**

Add a short section that explains:
- `full-csds 800` is a weak benchmark
- `full_csds_calibration_working_100.jsonl` is the AI-assisted review file
- `full_csds_calibrated_100.jsonl` is the higher-trust calibrated benchmark

Include the exact command:

```powershell
& 'D:\anaconda\envs\minimind_job_agent\python.exe' 'D:\minimind\.worktrees\minimind-job-agent\scripts\build_full_csds_calibrated_subset.py' `
  --csds-data-dir 'D:\minimind\.worktrees\minimind-job-agent\tmp_csds_download' `
  --split test `
  --baseline-case-results 'D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_csds_full_post_cache_move\20260410020844\case_results.jsonl' `
  --output-dir 'D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_csds_calibrated_100'
```

- [ ] **Step 6: Commit**

```bash
git -C D:\minimind\.worktrees\minimind-job-agent add scripts/build_full_csds_calibrated_subset.py tests/scripts/test_build_full_csds_calibrated_subset.py README.md
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "feat: add calibrated full-csds subset CLI"
```

### Task 4: Run verification and generate the real 100-case working set

**Files:**
- Verify only

- [ ] **Step 1: Run focused regression**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_calibrated_subset.py D:\minimind\.worktrees\minimind-job-agent\tests\scripts\test_build_full_csds_calibrated_subset.py -q`
Expected: PASS

- [ ] **Step 2: Run broader eval regression**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals -q`
Expected: PASS

- [ ] **Step 3: Run syntax verification**

Run: `python -m py_compile D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\calibrated_subset.py D:\minimind\.worktrees\minimind-job-agent\scripts\build_full_csds_calibrated_subset.py`
Expected: no output

- [ ] **Step 4: Generate the real working set**

Run:

```powershell
& 'D:\anaconda\envs\minimind_job_agent\python.exe' 'D:\minimind\.worktrees\minimind-job-agent\scripts\build_full_csds_calibrated_subset.py' `
  --csds-data-dir 'D:\minimind\.worktrees\minimind-job-agent\tmp_csds_download' `
  --split test `
  --baseline-case-results 'D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_csds_full_post_cache_move\20260410020844\case_results.jsonl' `
  --output-dir 'D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_csds_calibrated_100'
```

Expected:
- `full_csds_calibration_working_100.jsonl`
- summary printed with bucket counts and review-needed counts

- [ ] **Step 5: Commit**

```bash
git -C D:\minimind\.worktrees\minimind-job-agent add docs/superpowers/specs/2026-04-11-full-csds-calibrated-100-design.md docs/superpowers/plans/2026-04-11-full-csds-calibrated-100.md evals/sales_copilot/calibrated_subset.py scripts/build_full_csds_calibrated_subset.py tests/evals/test_calibrated_subset.py tests/scripts/test_build_full_csds_calibrated_subset.py README.md
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "feat: add calibrated full-csds benchmark tooling"
```
