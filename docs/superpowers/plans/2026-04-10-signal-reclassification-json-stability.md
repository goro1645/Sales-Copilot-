# Signal Reclassification JSON Stability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the DeepSeek second-pass signal reclassification step return valid JSON more reliably by adding explicit JSON response formatting, tolerant JSON extraction, and bounded retry behavior.

**Architecture:** Keep the reclassification pipeline structure unchanged. Improve only the LLM call boundary in `signal_reclassifier.py`: request JSON explicitly, tolerate common JSON wrapper formats, and retry a small number of times before falling back to the baseline parse result.

**Tech Stack:** Python, DeepSeek API, pytest

---

## File Map

- Modify: `D:/minimind/.worktrees/minimind-job-agent/evals/sales_copilot/signal_reclassifier.py`
- Test: `D:/minimind/.worktrees/minimind-job-agent/tests/evals/test_signal_reclassifier.py`

### Task 1: Add failing tests for JSON stability

**Files:**
- Modify: `D:/minimind/.worktrees/minimind-job-agent/tests/evals/test_signal_reclassifier.py`

- [ ] Add a test asserting `response_format={"type":"json_object"}` is passed to `llm_client.complete`.
- [ ] Add a test asserting fenced JSON content is parsed correctly.
- [ ] Add a test asserting the classifier retries after invalid JSON and succeeds on the next response.
- [ ] Run:

```powershell
& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_signal_reclassifier.py -q
```

Expected: FAIL before implementation.

### Task 2: Implement tolerant JSON extraction and retry logic

**Files:**
- Modify: `D:/minimind/.worktrees/minimind-job-agent/evals/sales_copilot/signal_reclassifier.py`

- [ ] Add a helper that first tries direct `json.loads`, then fenced-code-block extraction, then first-object extraction.
- [ ] Update `reclassify_signal_candidates(...)` to pass `response_format={"type":"json_object"}`.
- [ ] Add bounded retry behavior for empty/invalid JSON or missing `classified_signals`.
- [ ] Keep return shape unchanged so the runner and tests do not need a broader rewrite.
- [ ] Re-run the same targeted pytest command and expect PASS.

### Task 3: Verify no regression in the eval path

**Files:**
- Use current eval outputs under `D:/minimind/.worktrees/minimind-job-agent/evals/sales_copilot/`

- [ ] Run:

```powershell
& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_prompts.py -q
```

Expected: PASS.

- [ ] Re-run the `full-csds test` reclassification experiment and compare JSON validity against the previous reclassification run.
- [ ] Summarize whether JSON-stability improved enough to justify a second round of field-quality optimization.
