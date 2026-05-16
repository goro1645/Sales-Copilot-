# Sales Copilot Reader-Friendly Annotations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Sales Copilot 主线和关键评测文件补“阅读友好型”注释，帮助读代码和面试准备。

**Architecture:** 只补文件头说明、关键函数注释、术语解释和少量设计取舍说明，不改逻辑、不改接口。主线文件优先解释 workflow 和术语，评测文件优先解释 parse F1、retrieval recall 和 acceptable rate。

**Tech Stack:** Python, LangGraph, DeepSeek tool-call/streaming, local evaluation utilities

---

### Task 1: Annotate Mainline Workflow Entry Files

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\sales_copilot\runner.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\sales_copilot\state.py`

- [ ] Add file header comments that explain workflow entrypoints and shared state shape.
- [ ] Add concise comments on `run_sales_copilot`, `run_sales_copilot_stream`, `_run_parse_node`, `_run_evaluate_lead_node`, and `_run_followup_node`.
- [ ] Add inline glossary comments for state fields such as `meeting_summary`, `retrieved_docs`, `task_candidates`, and `task_payload`.

### Task 2: Annotate Workflow Node Graph

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\sales_copilot\graph.py`

- [ ] Add a file header explaining that `graph.py` contains the business node graph and state transitions.
- [ ] Add comments on the main nodes: ingest, parse, retrieve, memory load, lead evaluation, task-candidate build, follow-up, CRM write-back, dashboard output, and routing.
- [ ] Add “why” comments around `account_memory` loading, query construction from `confirmed_needs`, and task candidate merge behavior.
- [ ] Add glossary comments that clarify `confirmed_needs`, `next_steps`, `timeline_signals`, and `risk_flags`.

### Task 3: Annotate Prompt Builders

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\sales_copilot\prompts.py`

- [ ] Add a file header describing prompts as the contract between workflow state and model outputs.
- [ ] Add concise comments for parse, lead scoring, and follow-up prompt builders.
- [ ] Add inline comments near field guidance for `confirmed_needs`, `next_steps`, `budget_signals`, and `timeline_signals`.

### Task 4: Annotate Retrieval and Task Candidate Modules

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\sales_copilot\retrieval.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\sales_copilot\task_candidates.py`

- [ ] Add file headers explaining `hybrid retrieval + reranker` and `task_candidates` as a fact-preservation layer.
- [ ] Add comments on `hybrid_retrieve_rows`, `hybrid_rerank_retrieve_rows`, and `hybrid_retrieve_knowledge_chunks`, including the meaning of `hybrid_score`.
- [ ] Add comments on `build_task_candidates` and `build_tasks_from_candidates`, including why candidates are programmatic rather than another model generation step.

### Task 5: Annotate Evaluation Files

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\metrics.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\reporting.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\workflow_quality_judge.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\workflow_quality_reporting.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\retrieval_metrics.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\retrieval_runner.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\dual_path_query_builder.py`

- [ ] Add file headers explaining the three evaluation layers: parse extraction, retrieval, and workflow quality.
- [ ] Comment `_set_precision_recall_f1`, `_semantic_set_precision_recall_f1`, `evaluate_parse_case`, and `summarize_parse_metrics` to explain list-field F1 versus semantic F1.
- [ ] Comment retrieval benchmark files to explain `recall@k`, `MRR`, and `dual-path` query evaluation.
- [ ] Comment `evaluate_workflow_case` and `summarize_workflow_metrics` to explain route/task/CRM workflow metrics.
- [ ] Comment `reporting.py` to explain how case-level metrics are turned into human-readable bundles and reports.
- [ ] Comment `workflow_quality_judge.py` to explain Stage 1 vs Stage 2 judging and how `acceptable rate` is derived from 1–5 scores in downstream reporting.

### Task 6: Verify Syntax

**Files:**
- Verify: all modified files above

- [ ] Run `py_compile` across the touched files.
- [ ] Confirm no syntax errors before reporting completion.
