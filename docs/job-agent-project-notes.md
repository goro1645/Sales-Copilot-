# MiniMind Job Agent Notes

## What this project does

This feature extends MiniMind from a lightweight model project into a small LLM application system.
It supports:

- Job description parsing
- Resume fit scoring
- Resume rewriting
- Cover letter generation
- SQLite-based application tracking
- A CLI demo for end-to-end verification

## Why LangGraph is used

LangGraph is a good fit here because the workflow is stateful and conditional:

- Low match jobs should be rejected early
- Medium match jobs should rewrite the resume only
- High match jobs should rewrite the resume and generate a cover letter

This is easier to reason about as a graph than as one large prompt or a single script with nested branching.

## Core files

- `agent/state.py`: shared graph state
- `agent/graph.py`: workflow nodes and routing
- `agent/prompts.py`: prompt templates for MiniMind API generation
- `agent/runner.py`: graph entrypoint and optional MiniMind API generator
- `agent/storage.py`: SQLite persistence
- `scripts/openai_api_utils.py`: OpenAI-style tool-calling helpers
- `scripts/job_agent_demo.py`: CLI demo
- `scripts/job_agent_web_demo.py`: Streamlit dashboard

## Local verification

Run tests:

```powershell
pytest D:\minimind\.worktrees\minimind-job-agent\tests -q
```

Run the deterministic demo:

```powershell
python D:\minimind\.worktrees\minimind-job-agent\scripts\job_agent_demo.py `
  --company "MiniMind Labs" `
  --role "LLM Application Engineer" `
  --job-posting "D:\minimind\.worktrees\minimind-job-agent\data\job_agent\sample_jd.md" `
  --resume-text "D:\minimind\.worktrees\minimind-job-agent\data\job_agent\sample_resume.md"
```

Run with MiniMind API generation enabled after starting `scripts/serve_openai_api.py`:

```powershell
python D:\minimind\.worktrees\minimind-job-agent\scripts\job_agent_demo.py `
  --company "MiniMind Labs" `
  --role "LLM Application Engineer" `
  --job-posting "D:\minimind\.worktrees\minimind-job-agent\data\job_agent\sample_jd.md" `
  --resume-text "D:\minimind\.worktrees\minimind-job-agent\data\job_agent\sample_resume.md" `
  --use-api-generation `
  --api-base-url "http://127.0.0.1:8998/v1" `
  --api-model "minimind"
```

Run the Streamlit dashboard:

```powershell
streamlit run D:\minimind\.worktrees\minimind-job-agent\scripts\job_agent_web_demo.py
```

## Resume framing

Recommended project title:

`MiniMind LangGraph Job Agent`

Recommended short description:

`Built a LangGraph-based job application copilot on top of MiniMind, supporting JD parsing, resume scoring, resume rewriting, cover letter generation, and SQLite-based application tracking.`
