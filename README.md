# Sales Copilot

LangGraph-based sales follow-up workflow agent with MCP-backed CRM tools, a local Streamlit workbench, and offline evaluation on the public real Chinese customer-service corpus `CSDS`.

## What This Project Does

This project focuses on the execution loop behind an enterprise sales copilot instead of a single-turn chat demo. It turns customer context and meeting notes into structured fields, lead signals, follow-up actions, CRM state updates, and task creation.

The core workflow covers:

`customer profile -> meeting-note parsing -> lead scoring -> follow-up planning -> CRM write-back -> task creation`

## Highlights

- Built a stateful sales follow-up workflow with `LangGraph`, including parsing, routing, follow-up planning, CRM write-back, and task generation.
- Added a local `CRM/Tasks MCP` tool layer so the agent reads and writes business state through standardized tool calls instead of direct ad-hoc database updates.
- Built a local `Streamlit + SQLite` workbench for inspecting lead score, stage, CRM updates, tasks, and workflow traces.
- Designed customer-service-oriented parsing prompts and JSON schema constraints for fields such as `confirmed_needs`, `next_steps`, `budget_signals`, and `timeline_signals`.
- Added offline evaluation pipelines for both self-built golden cases and public real customer-service data.

## Evaluation

### Public Real Corpus: CSDS

The repository includes a `full-CSDS` parse-only evaluation path over the official `CSDS` dataset.

Latest validated result on the official `test` split (`800` samples):

- `JSON valid rate = 100%`
- `Average list-field F1 = 80.3%`

Field groups include:

- `confirmed_needs`
- `next_steps`
- `budget_signals`
- `timeline_signals`
- `customer_roles`

This evaluation is used to validate structured extraction quality on public real customer-service conversations rather than synthetic prompts.

### Workflow Evaluation

Workflow behaviors such as route selection, CRM write-back, and task creation are evaluated separately on self-built golden cases, because public customer-service corpora do not provide direct labels for sales workflow execution.

## System Design

### Workflow Layer

`sales_copilot/graph.py` orchestrates the end-to-end workflow:

- parse meeting notes
- retrieve account context
- score lead state
- plan follow-up actions
- write CRM state
- create tasks
- prepare dashboard output

### LLM Layer

The project currently uses `DeepSeek API` for structured parsing and follow-up generation. Prompt templates are defined in:

- `sales_copilot/prompts.py`

### MCP Tool Layer

The local MCP-backed CRM tool path is used for:

- account lookup
- task lookup
- task creation
- account stage/status update

This makes the agent easier to explain as an execution-oriented system rather than a text-only assistant.

### Local Workbench

The local demo is built with:

- `Streamlit` for the UI
- `SQLite` for account/task/meeting persistence

Main entrypoints:

- `scripts/sales_copilot_web_demo.py`
- `scripts/run_sales_copilot_eval.py`

## Quick Start

### 1. Environment

Use the Python environment that contains the project dependencies and set:

```powershell
$env:DEEPSEEK_API_KEY="your_key"
```

### 2. Run the Local Demo

```powershell
python -m streamlit run scripts/sales_copilot_web_demo.py
```

### 3. Run CSDS Evaluation

For the official `CSDS` dataset:

```powershell
python scripts/run_sales_copilot_eval.py `
  --dataset-kind full-csds `
  --csds-data-dir /path/to/csds `
  --csds-splits test `
  --output-dir evals/sales_copilot/outputs_csds_full `
  --mode offline
```

## Repository Map

- `sales_copilot/`: workflow, prompts, storage, MCP integration
- `scripts/sales_copilot_web_demo.py`: local Streamlit demo
- `scripts/run_sales_copilot_eval.py`: offline evaluation entrypoint
- `evals/sales_copilot/`: adapters, metrics, runners, evaluation outputs

## Why This Repo Still Contains MiniMind

This project was developed on top of the `MiniMind` codebase and keeps the relevant local-model and serving utilities for reproducibility. The repository homepage is rewritten to foreground the `Sales Copilot` application layer, while upstream training and serving components remain available in the codebase.

## Acknowledgement

This work is built on top of the open-source `MiniMind` project:

- [MiniMind upstream repository](https://github.com/jingyaogong/minimind)
