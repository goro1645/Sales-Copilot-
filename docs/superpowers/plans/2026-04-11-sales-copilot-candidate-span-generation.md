# Sales Copilot Candidate Span Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a CSDS parse-only experiment that asks DeepSeek for multiple candidate spans, scores them locally, and projects only budget/timeline refinements for a 20-case smoke run.

**Architecture:** Keep the baseline parse path unchanged, then layer a candidate-span refinement step after parse for CSDS evaluation only. The model proposes multiple verbatim spans through a strict tool-call schema; local Python scoring validates, filters, and selects top candidates before bounded projection into `budget_signals` and `timeline_signals`.

**Tech Stack:** Python, DeepSeek tool calls, existing CSDS parse-only evaluation pipeline, pytest

---

### Task 1: Add failing tests for candidate-span refinement

**Files:**
- Create: `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_candidate_span_refiner.py`

- [ ] **Step 1: Write the failing test**

```python
def test_generate_candidates_uses_tool_call_schema():
    ...


def test_filter_candidates_discards_non_source_spans():
    ...


def test_score_candidates_prefers_short_pure_timeline_span():
    ...


def test_project_candidates_only_updates_budget_and_timeline():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_candidate_span_refiner.py -q`
Expected: FAIL with import or missing function errors for candidate refinement helpers.

- [ ] **Step 3: Commit**

```bash
git -C D:\minimind\.worktrees\minimind-job-agent add tests/evals/test_candidate_span_refiner.py
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "test: cover candidate span refinement experiment"
```

### Task 2: Implement candidate-span refinement module

**Files:**
- Create: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\candidate_span_refiner.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\sales_copilot\prompts.py`

- [ ] **Step 1: Write minimal implementation**

```python
def generate_signal_candidates(...): ...
def validate_candidate(...): ...
def score_candidate(...): ...
def select_field_candidates(...): ...
def refine_parse_result_with_candidates(...): ...
```

Add a prompt builder that asks for multiple verbatim source-note spans via a strict tool-call schema.

- [ ] **Step 2: Run targeted tests**

Run: `pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_candidate_span_refiner.py -q`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git -C D:\minimind\.worktrees\minimind-job-agent add evals/sales_copilot/candidate_span_refiner.py sales_copilot/prompts.py tests/evals/test_candidate_span_refiner.py
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "feat: add candidate span refinement experiment"
```

### Task 3: Thread candidate refinement through CSDS evaluation

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\csds_runner.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\scripts\run_sales_copilot_eval.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_csds_runner.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\tests\scripts\test_run_sales_copilot_eval.py`

- [ ] **Step 1: Write failing integration tests**

```python
def test_run_csds_parse_evaluation_candidate_refinement_when_enabled(...): ...


def test_main_threads_candidate_refinement_flag(...): ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
`pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_csds_runner.py D:\minimind\.worktrees\minimind-job-agent\tests\scripts\test_run_sales_copilot_eval.py -q`
Expected: FAIL because the new flag and refinement hook do not exist yet.

- [ ] **Step 3: Implement minimal wiring**

Add:
- `use_candidate_generation_refinement` parameter in CSDS runner helpers
- `--use-candidate-generation-refinement` CLI flag
- a refinement call after baseline parse and before metric evaluation
- fallback to baseline parse on refinement failure

- [ ] **Step 4: Re-run targeted tests**

Run:
`pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_csds_runner.py D:\minimind\.worktrees\minimind-job-agent\tests\scripts\test_run_sales_copilot_eval.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C D:\minimind\.worktrees\minimind-job-agent add evals/sales_copilot/csds_runner.py scripts/run_sales_copilot_eval.py tests/evals/test_csds_runner.py tests/scripts/test_run_sales_copilot_eval.py
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "feat: wire candidate span refinement into CSDS eval"
```

### Task 4: Run verification and 20-case smoke

**Files:**
- Verify only

- [ ] **Step 1: Run focused regression**

Run:
`pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals D:\minimind\.worktrees\minimind-job-agent\tests\scripts\test_run_sales_copilot_eval.py -q`
Expected: PASS

- [ ] **Step 2: Run syntax verification**

Run:
`python -m py_compile D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\candidate_span_refiner.py D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\csds_runner.py D:\minimind\.worktrees\minimind-job-agent\scripts\run_sales_copilot_eval.py D:\minimind\.worktrees\minimind-job-agent\sales_copilot\prompts.py`
Expected: no output

- [ ] **Step 3: Run 20-case smoke evaluation**

Run:

```powershell
$env:DEEPSEEK_API_KEY="YOUR_KEY"
$env:HF_HOME="D:\hf_cache\huggingface"
$env:SENTENCE_TRANSFORMERS_HOME="D:\hf_cache\sentence_transformers"
& 'D:\anaconda\envs\minimind_job_agent\python.exe' 'D:\minimind\.worktrees\minimind-job-agent\scripts\run_sales_copilot_eval.py' `
  --dataset-kind full-csds `
  --csds-data-dir 'D:\minimind\.worktrees\minimind-job-agent\tmp_csds_download' `
  --csds-splits test `
  --limit 20 `
  --output-dir 'D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_csds_candidate_span_smoke' `
  --mode offline `
  --use-candidate-generation-refinement
```

Expected:
- `json_valid_rate` remains `1.0`
- no top-level parse failures
- report bundle generated under the smoke output directory

- [ ] **Step 4: Inspect at least one known problematic case**

Inspect:
- `csds_full_test_9345`

Confirm whether:
- timeline span is finer-grained than the baseline sentence-level form
- `next_steps` remains baseline-safe

- [ ] **Step 5: Commit**

```bash
git -C D:\minimind\.worktrees\minimind-job-agent add docs/superpowers/specs/2026-04-11-sales-copilot-candidate-span-generation-design.md docs/superpowers/plans/2026-04-11-sales-copilot-candidate-span-generation.md evals/sales_copilot/candidate_span_refiner.py evals/sales_copilot/csds_runner.py sales_copilot/prompts.py scripts/run_sales_copilot_eval.py tests/evals/test_candidate_span_refiner.py tests/evals/test_csds_runner.py tests/scripts/test_run_sales_copilot_eval.py
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "feat: add candidate span refinement smoke experiment"
```
