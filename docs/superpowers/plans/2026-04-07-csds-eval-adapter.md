# CSDS Eval Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `CSDS`-backed parse-only evaluation path to the existing `Sales Copilot` offline evaluation framework.

**Architecture:** Keep the current `golden_cases` workflow benchmark unchanged. Introduce a separate `CSDS` adapter and parse-only runner that reuse the existing parse node and parse metrics, then expose a dedicated CLI path for `CSDS`.

**Tech Stack:** Python, pytest, JSONL, existing Sales Copilot parse node, existing parse metrics

---

## File Structure

- Create: `evals/sales_copilot/csds_cases.jsonl`
  - small normalized subset derived from official `CSDS`
- Create: `evals/sales_copilot/csds_adapter.py`
  - load and validate normalized `CSDS` rows
- Create: `evals/sales_copilot/csds_runner.py`
  - parse-only evaluation runner
- Modify: `scripts/run_sales_copilot_eval.py`
  - add a `csds` dataset mode
- Create: `tests/evals/test_csds_adapter.py`
  - adapter coverage
- Create: `tests/evals/test_csds_runner.py`
  - runner coverage
- Modify: `README.md`
  - document `CSDS` usage and reporting boundary

### Task 1: Add Local CSDS Subset And Adapter

**Files:**
- Create: `evals/sales_copilot/csds_cases.jsonl`
- Create: `evals/sales_copilot/csds_adapter.py`
- Test: `tests/evals/test_csds_adapter.py`

- [ ] **Step 1: Write failing adapter tests**
- [ ] **Step 2: Add a small normalized `CSDS` subset with source metadata**
- [ ] **Step 3: Implement adapter loader and validation**
- [ ] **Step 4: Run adapter tests**
- [ ] **Step 5: Commit**

### Task 2: Add Parse-Only CSDS Runner

**Files:**
- Create: `evals/sales_copilot/csds_runner.py`
- Test: `tests/evals/test_csds_runner.py`

- [ ] **Step 1: Write failing runner tests for parse-only summary generation**
- [ ] **Step 2: Implement the runner on top of the existing parse node and parse metrics**
- [ ] **Step 3: Run runner tests**
- [ ] **Step 4: Commit**

### Task 3: Wire CLI Support

**Files:**
- Modify: `scripts/run_sales_copilot_eval.py`
- Modify: `tests/evals/test_sales_copilot_runner.py`

- [ ] **Step 1: Add a failing CLI/help test for `csds` mode**
- [ ] **Step 2: Add `csds` dataset selection and dispatch to the new runner**
- [ ] **Step 3: Run eval tests**
- [ ] **Step 4: Commit**

### Task 4: Document Reporting Boundary

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document `CSDS` command usage**
- [ ] **Step 2: Document that `CSDS` is parse-only and not workflow accuracy**
- [ ] **Step 3: Run README sanity check**
- [ ] **Step 4: Commit**

## Self-Review

### Spec Coverage

- local `CSDS` subset: covered in Task 1
- dedicated adapter: covered in Task 1
- parse-only runner: covered in Task 2
- CLI integration: covered in Task 3
- reporting boundary: covered in Task 4

### Placeholder Scan

- no `TODO` / `TBD`
- tasks map directly to concrete files
- scope intentionally excludes `CSDS` workflow evaluation

### Type Consistency

- `CSDS` path remains parse-only
- existing `GoldenCase` workflow path remains unchanged
- CLI will add dataset selection, not overload workflow semantics
