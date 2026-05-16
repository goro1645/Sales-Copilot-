# Sales Copilot Reader-Friendly Annotations Design

## Goal

为 Sales Copilot 主线代码和关键评测代码补一层“阅读友好型”注释，帮助读代码的人快速理解：

- 每个文件在整体系统中的位置
- 关键函数在 workflow / eval 链路中的职责
- 项目内专用术语的含义
- parse 评测、retrieval 评测、workflow 质量评测分别在测什么

## Scope

本轮覆盖主线与评测链中最常读的 13 个文件：

### 主线执行链

- `sales_copilot/runner.py`
- `sales_copilot/graph.py`
- `sales_copilot/state.py`
- `sales_copilot/prompts.py`
- `sales_copilot/retrieval.py`
- `sales_copilot/task_candidates.py`

### 评测链

- `evals/sales_copilot/metrics.py`
- `evals/sales_copilot/reporting.py`
- `evals/sales_copilot/workflow_quality_judge.py`
- `evals/sales_copilot/workflow_quality_reporting.py`
- `evals/sales_copilot/retrieval_metrics.py`
- `evals/sales_copilot/retrieval_runner.py`
- `evals/sales_copilot/dual_path_query_builder.py`

## Non-Goals

- 不修改业务逻辑
- 不重命名现有字段或函数
- 不大规模重构文件结构
- 不给每一个 helper 都加逐行解释

## Annotation Strategy

### 1. File Header Comments

在每个目标文件顶部增加简短文件说明，回答：

- 这个文件在系统中负责什么
- 读这个文件时最该关注哪条主线
- 它与上游 / 下游怎么衔接

### 2. Key Function Comments

只给阅读路径上的关键函数增加短注释，重点解释“作用”和“边界”，而不是复述代码。

主线文件重点函数：

- `run_sales_copilot`
- `run_sales_copilot_stream`
- `parse_meeting_note_node`
- `retrieve_context_node`
- `load_account_memory_node`
- `evaluate_lead_node`
- `build_task_candidates_node`
- `route_after_lead_evaluation`
- `build_*_messages`
- `hybrid_retrieve_knowledge_chunks`
- `build_task_candidates`
- `build_tasks_from_candidates`

评测文件重点函数：

- `evaluate_parse_case`
- `summarize_parse_metrics`
- `evaluate_workflow_case`
- `summarize_workflow_metrics`
- `_build_report_markdown`
- `write_report_bundle`
- `build_stage1_messages`
- `build_stage2_messages`
- `parse_stage1_result`
- `parse_stage2_alignment`

### 3. Glossary-Style Inline Comments

对项目内专用术语在首次关键使用处补简短注释，例如：

- `confirmed_needs`
- `next_steps`
- `timeline_signals`
- `budget_signals`
- `task_candidates`
- `account_memory`
- `retrieved_docs`
- `list-field F1`
- `semantic F1`
- `recall@k`
- `overall acceptable rate`
- `CRM acceptable rate`

### 4. “Why” Comments for Design Choices

只在容易被误解的地方补“为什么这样做”，例如：

- 为什么 account memory 是按 `account_id` 直接读取，而不是向量检索
- 为什么 task candidates 是程序构造的中间层
- 为什么 workflow quality judge 分两阶段

## Expected Outcome

完成后，读代码的人应该能较顺畅地回答：

- Sales Copilot workflow 从输入到 CRM/tasks 是怎么跑的
- RAG query 是怎么构造的，retrieved docs 来自哪里
- `task_candidates` 为什么会让任务生成更具体
- parse F1、retrieval recall、acceptable rate 分别代表什么

## Verification

- 运行 `py_compile` 检查所有修改过的 Python 文件语法
- 只做注释修改，不要求跑完整功能测试
