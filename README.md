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

### Retrieval Benchmark

Sales Copilot includes a dedicated retrieval benchmark for the local product/playbook knowledge base.

It compares:

- `keyword_only`
- `hybrid`
- `hybrid_rerank`

Metrics:

- `Recall@1`
- `Recall@3`
- `Recall@5`
- `MRR`

There are now two retrieval case sets:

- `retrieval_cases.jsonl`
  - small sanity benchmark for baseline regression checks
- `retrieval_cases_csds_hard.jsonl`
  - `CSDS`-derived hard benchmark built from public real customer-service phrasing plus manual labels
  - includes `product_hard`, `playbook_hard`, and `cross_source_confusing` buckets
  - designed to show whether `hybrid_rerank` improves top-rank ordering over plain `hybrid`

Run:

```powershell
python scripts/run_sales_copilot_retrieval_eval.py `
  --cases evals/sales_copilot/retrieval_cases.jsonl `
  --db-path data/sales_copilot/sales_copilot.db `
  --output-dir evals/sales_copilot/outputs_retrieval
```

Run the CSDS-derived hard set:

```powershell
python scripts/run_sales_copilot_retrieval_eval.py `
  --cases evals/sales_copilot/retrieval_cases_csds_hard.jsonl `
  --db-path data/sales_copilot/sales_copilot.db `
  --output-dir evals/sales_copilot/outputs_retrieval_hard
```

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

### Hybrid Retrieval

Sales Copilot now supports hybrid retrieval for product knowledge and sales playbook chunks.

- Vector similarity is provided by `sentence-transformers`
- Keyword retrieval remains as a deterministic fallback
- Cached embeddings are stored in SQLite through `knowledge_chunk_embeddings`
- The workflow demo path loads the default embedder through `sales_copilot/runner.py`
- Direct graph tests can still force keyword-only retrieval to keep regression runs stable

To rebuild cached embeddings:

```powershell
python scripts/rebuild_sales_copilot_embeddings.py --db-path data/sales_copilot/sales_copilot.db
```

### Cross-Encoder Reranker

Sales Copilot now also supports a local second-stage reranker.

- first-stage recall remains `keyword_only` or `hybrid`
- second-stage reranking uses a lightweight local cross-encoder
- benchmark mode name: `hybrid_rerank`

This keeps retrieval architecture explicit:

- recall finds the candidate set
- reranking improves top-rank ordering inside that candidate set

The reranker is optional at runtime and falls back to plain `hybrid` if the local model cannot be loaded.

### MCP Tool Layer

The local MCP-backed CRM tool path is used for:

- account lookup
- task lookup
- task creation
- account stage/status update

This makes the agent easier to explain as an execution-oriented system rather than a text-only assistant.

### stdio MCP Server

The repository now also includes a real `stdio` MCP server entrypoint for the CRM/Tasks tool surface:

- `sales_copilot/mcp_stdio_server.py`
- `scripts/run_sales_copilot_mcp_server.py`

The exposed tools are:

- `get_account`
- `list_account_tasks`
- `create_task`
- `update_account_stage`

This path provides:

- tool discovery
- tool schema
- standard tool invocation
- real client-server validation over `stdio`

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

### 2.5 Run the DeepSeek Streaming Tool-Call Demo

This repository also includes a standalone DeepSeek official SSE demo that:

- streams normal text deltas
- streams `tool_calls`
- executes local CRM/knowledge-style tools after streamed tool completion
- sends the tool result back for a second streamed answer

Run:

```powershell
python scripts/deepseek_stream_tool_demo.py
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

### 4. Run the stdio MCP Server

Install the MCP SDK from the official PyPI index instead of the Tsinghua mirror if your network path is international:

```powershell
python -m pip install --index-url https://pypi.org/simple mcp
```

Then start the MCP server:

```powershell
python scripts/run_sales_copilot_mcp_server.py --db-path data/sales_copilot/sales_copilot.db
```

Notes:

- The MCP SDK is treated as an optional runtime dependency for the stdio server path.
- We do not force it into the main app startup path, so the existing Streamlit/FastAPI flows stay isolated from MCP transport concerns.
- In the validated local environment, `mcp` works with `starlette==0.46.2`; avoid blindly upgrading `starlette` to `1.x` if you still rely on `fastapi==0.115.12`.

## Repository Map

- `sales_copilot/`: workflow, prompts, storage, MCP integration
- `sales_copilot/mcp_stdio_server.py`: stdio MCP server wrapper
- `scripts/sales_copilot_web_demo.py`: local Streamlit demo
- `scripts/run_sales_copilot_eval.py`: offline evaluation entrypoint
- `scripts/run_sales_copilot_mcp_server.py`: stdio MCP server entrypoint
- `evals/sales_copilot/`: adapters, metrics, runners, evaluation outputs

## Why This Repo Still Contains MiniMind

This project was developed on top of the `MiniMind` codebase and keeps the relevant local-model and serving utilities for reproducibility. The repository homepage is rewritten to foreground the `Sales Copilot` application layer, while upstream training and serving components remain available in the codebase.

## Acknowledgement

This work is built on top of the open-source `MiniMind` project:

- [MiniMind upstream repository](https://github.com/jingyaogong/minimind)
