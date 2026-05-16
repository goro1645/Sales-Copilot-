# Sales Copilot

一个面向销售跟进场景的 LLM Agent 项目，输入客户资料与会议纪要，输出结构化解析、跟进建议、CRM 写回和待办任务。

项目重点不在单轮聊天，而在完整 workflow：结构化解析、检索增强、机会判断、任务生成、业务状态写回，以及对应的离线评测体系。

## 项目简介

这个项目尝试把“销售会议之后该怎么跟进”做成一个可运行、可观察、可评测的 Agent 系统。

给定一段客户背景和会议纪要，系统会：

- 解析会议中的需求、时间线、预算和下一步动作
- 检索产品知识和销售手册，为判断提供上下文
- 生成机会阶段、风险信号和跟进建议
- 把结果写回 CRM 状态与任务系统
- 在本地工作台中展示流式执行过程和最终结果

## 核心能力

- 结构化会议纪要解析：抽取 `confirmed_needs`、`next_steps`、`budget_signals`、`timeline_signals` 等关键信号
- Hybrid RAG：结合产品知识和销售手册，为机会判断和跟进建议提供证据支撑
- 基于 `task_candidates` 的任务生成：减少会议事实在最终待办生成中的丢失
- CRM / Tasks 写回：将机会阶段、跟进建议和任务结果落入业务状态层
- Streamlit 工作台与流式执行观察：支持查看 workflow 阶段、任务结果和调试信息

## 系统流程

`客户资料 -> 会议纪要解析 -> 检索上下文 -> 机会判断 -> 跟进计划 -> CRM / Tasks 写回`

## 评测设计

项目同时使用公开数据集和自建评测集：

- 公开数据集用于验证结构化解析质量
- 自建评测集用于验证检索效果以及最终 workflow 输出质量
- 评测覆盖解析、检索和最终业务输出三个层面

首页不展开具体分数和内部 benchmark 命名，详细实验与复盘见下方文档链接。

## 代码结构

- `sales_copilot/`：主 workflow、状态流转、检索、任务生成、流式接口
- `evals/sales_copilot/`：结构化解析、检索与 workflow 评测
- `scripts/`：运行、评测与本地工具脚本
- `docs/`：复盘、设计文档与实现计划

## 快速运行

1. 启动流式 API

```powershell
python scripts/run_sales_copilot_stream_api.py --host 127.0.0.1 --port 8011
```

2. 启动本地工作台

```powershell
python -m streamlit run scripts/sales_copilot_web_demo.py --server.port 8501
```

3. 浏览器打开 `http://127.0.0.1:8501`

## 进一步阅读

- `docs/sales-copilot-retrospective.md`
- `docs/superpowers/specs/`
- `docs/superpowers/plans/`

## 适合关注的内容

如果你更关心 LLM / RAG / 评测能力，建议优先看：

- `sales_copilot/graph.py`
- `sales_copilot/retrieval.py`
- `sales_copilot/task_candidates.py`
- `evals/sales_copilot/metrics.py`
- `evals/sales_copilot/workflow_quality_judge.py`
