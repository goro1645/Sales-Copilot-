# Full-CSDS Gold Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reproducible audit toolchain that samples 50 stratified `full-csds` test cases, preserves raw source summaries plus generated `expected_parse`, and emits summary statistics for overlap-heavy weak-gold signals.

**Architecture:** Reuse `load_full_csds_cases()` as the single source of adapted cases, then layer a focused `gold_audit.py` module on top for bucketing, deterministic sample selection, heuristic-flag generation, and summary output. Keep this separate from main evaluation logic so we can audit benchmark quality without perturbing parse or workflow code paths.

**Tech Stack:** Python, existing CSDS adapter, pytest, JSONL/JSON output

---

### Task 1: Add failing tests for audit bucketing and sampling

**Files:**
- Create: `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_gold_audit.py`

- [ ] **Step 1: Write the failing test**

```python
def test_assign_audit_bucket_prioritizes_overlap_cases():
    ...


def test_build_audit_sample_preserves_requested_bucket_sizes():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_gold_audit.py -q`
Expected: FAIL with missing module/function errors for `gold_audit`.

- [ ] **Step 3: Commit**

```bash
git -C D:\minimind\.worktrees\minimind-job-agent add tests/evals/test_gold_audit.py
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "test: cover full-csds gold audit sampling"
```

### Task 2: Implement gold-audit helpers

**Files:**
- Create: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\gold_audit.py`
- Test: `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_gold_audit.py`

- [ ] **Step 1: Write minimal implementation**

```python
def assign_audit_bucket(case: dict[str, object]) -> str:
    ...


def build_full_csds_gold_audit_sample(cases: list[dict[str, object]]) -> list[dict[str, object]]:
    ...
```

Include:
- deterministic bucket assignment
- stratified sample selection
- preservation of `meeting_note_text`, `expected_parse`, and raw summary lists

- [ ] **Step 2: Run targeted tests**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_gold_audit.py -q`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git -C D:\minimind\.worktrees\minimind-job-agent add evals/sales_copilot/gold_audit.py tests/evals/test_gold_audit.py
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "feat: add full-csds gold audit helpers"
```

### Task 3: Add heuristic flags and summary generation

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\gold_audit.py`
- Test: `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_gold_audit.py`

- [ ] **Step 1: Write the failing test**

```python
def test_build_audit_row_marks_overlap_flags():
    ...


def test_summarize_gold_audit_counts_overlap_and_warning_flags():
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_gold_audit.py -q`
Expected: FAIL because heuristic flagging and summary helpers do not exist yet.

- [ ] **Step 3: Implement minimal code**

```python
def build_audit_row(case: dict[str, object]) -> dict[str, object]:
    ...


def summarize_gold_audit_rows(rows: list[dict[str, object]]) -> dict[str, object]:
    ...
```

Include:
- overlap flags for `timeline_next_overlap` and `budget_next_overlap`
- simple suspicion flags for timeline/budget misuse
- blank `audit_label` and `audit_note` fields

- [ ] **Step 4: Re-run tests**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_gold_audit.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C D:\minimind\.worktrees\minimind-job-agent add evals/sales_copilot/gold_audit.py tests/evals/test_gold_audit.py
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "feat: add heuristic summaries for gold audit"
```

### Task 4: Add CLI entrypoint and documentation

**Files:**
- Create: `D:\minimind\.worktrees\minimind-job-agent\scripts\build_full_csds_gold_audit.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\README.md`

- [ ] **Step 1: Write the failing test**

```python
def test_build_full_csds_gold_audit_cli_writes_sample_and_summary(tmp_path):
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\scripts\test_build_full_csds_gold_audit.py -q`
Expected: FAIL with missing script/module errors.

- [ ] **Step 3: Implement minimal CLI**

```python
def main() -> int:
    ...
```

The CLI should:
- load `full-csds` cases for the requested split
- build the stratified sample
- write `full_csds_gold_audit_sample.jsonl`
- write `full_csds_gold_audit_summary.json`

- [ ] **Step 4: Re-run tests**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\scripts\test_build_full_csds_gold_audit.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C D:\minimind\.worktrees\minimind-job-agent add scripts/build_full_csds_gold_audit.py tests/scripts/test_build_full_csds_gold_audit.py README.md
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "feat: add full-csds gold audit CLI"
```

### Task 5: Run verification and generate a real test-split audit sample

**Files:**
- Verify only

- [ ] **Step 1: Run focused regression**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_gold_audit.py D:\minimind\.worktrees\minimind-job-agent\tests\scripts\test_build_full_csds_gold_audit.py -q`
Expected: PASS

- [ ] **Step 2: Run broader eval regression**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals -q`
Expected: PASS

- [ ] **Step 3: Run syntax verification**

Run: `python -m py_compile D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\gold_audit.py D:\minimind\.worktrees\minimind-job-agent\scripts\build_full_csds_gold_audit.py`
Expected: no output

- [ ] **Step 4: Generate real audit artifacts**

Run:

```powershell
& 'D:\anaconda\envs\minimind_job_agent\python.exe' 'D:\minimind\.worktrees\minimind-job-agent\scripts\build_full_csds_gold_audit.py' `
  --csds-data-dir 'D:\minimind\.worktrees\minimind-job-agent\tmp_csds_download' `
  --split test `
  --output-dir 'D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_csds_gold_audit'
```
Expected:
- `full_csds_gold_audit_sample.jsonl`
- `full_csds_gold_audit_summary.json`

- [ ] **Step 5: Commit**

```bash
git -C D:\minimind\.worktrees\minimind-job-agent add docs/superpowers/specs/2026-04-11-full-csds-gold-audit-design.md docs/superpowers/plans/2026-04-11-full-csds-gold-audit.md evals/sales_copilot/gold_audit.py scripts/build_full_csds_gold_audit.py tests/evals/test_gold_audit.py tests/scripts/test_build_full_csds_gold_audit.py README.md
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "feat: add full-csds gold audit tooling"
```
