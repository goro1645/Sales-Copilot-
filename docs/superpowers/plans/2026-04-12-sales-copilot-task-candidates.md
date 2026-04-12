# Sales Copilot Task Candidates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic `task_candidates` middle layer that grounds follow-up task generation in meeting-derived actions and improves workflow task quality on the artificial sales benchmark.

**Architecture:** Introduce one focused helper module for candidate extraction and candidate-to-task materialization, thread `task_candidates` through workflow state, then update the graph and prompt so follow-up planning consumes and merges those candidates before final task writeback.

**Tech Stack:** Python, LangGraph, existing Sales Copilot workflow, pytest

---

### Task 1: Add task-candidate helper module with deterministic extraction and task materialization

**Files:**
- Create: `D:\minimind\.worktrees\minimind-job-agent\sales_copilot\task_candidates.py`
- Create: `D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_task_candidates.py`

- [ ] **Step 1: Write the failing tests**

```python
from sales_copilot.task_candidates import build_task_candidates, build_tasks_from_candidates


def test_build_task_candidates_prefers_meeting_actions_and_dedupes() -> None:
    meeting_summary = {
        "next_steps": [
            "schedule technical deep-dive next week",
            "send tailored proposal by Friday",
            "schedule technical deep-dive next week",
        ],
        "confirmed_needs": ["need security review package", "want integration details"],
    }

    candidates = build_task_candidates(
        meeting_summary=meeting_summary,
        risk_flags=["stakeholder_missing"],
        lead_priority="high",
        opportunity_stage="proposal",
    )

    assert [row["text"] for row in candidates] == [
        "schedule technical deep-dive next week",
        "send tailored proposal by Friday",
        "need security review package",
        "identify missing decision makers",
    ]
    assert candidates[0]["task_type"] == "customer_meeting"
    assert candidates[1]["task_type"] == "proposal_or_quote"
    assert candidates[2]["task_type"] == "internal_prep"
    assert candidates[3]["task_type"] == "risk_mitigation"


def test_build_tasks_from_candidates_materializes_specific_titles() -> None:
    tasks = build_tasks_from_candidates(
        [
            {
                "text": "send tailored proposal by Friday",
                "source": "meeting_next_steps",
                "task_type": "proposal_or_quote",
                "priority_hint": "high",
                "timing_hint": "this_week",
                "evidence": ["Customer asked for a tailored proposal by Friday."],
            },
            {
                "text": "schedule technical deep-dive next week",
                "source": "meeting_next_steps",
                "task_type": "customer_meeting",
                "priority_hint": "high",
                "timing_hint": "next_week",
                "evidence": ["Customer wants a technical deep-dive next week."],
            },
        ]
    )

    assert tasks[0]["title"] == "Send tailored proposal"
    assert "Customer asked for a tailored proposal" in tasks[0]["description"]
    assert tasks[0]["priority"] == "high"
    assert tasks[1]["title"] == "Schedule technical deep-dive"
    assert tasks[1]["owner"] == "Sales"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```powershell
pytest D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_task_candidates.py -q
```

Expected:

- collection succeeds
- failure because `sales_copilot.task_candidates` does not exist yet

- [ ] **Step 3: Write the minimal implementation**

```python
from __future__ import annotations

from datetime import date, timedelta
from typing import Any


def _normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        output.append(item)
    return output


def _infer_task_type(text: str) -> str:
    lowered = text.lower()
    if any(token in lowered for token in ("proposal", "quote", "pricing")):
        return "proposal_or_quote"
    if any(token in lowered for token in ("meeting", "demo", "deep-dive", "deep dive", "workshop")):
        return "customer_meeting"
    if any(token in lowered for token in ("security", "integration", "architecture", "materials", "package")):
        return "internal_prep"
    if any(token in lowered for token in ("identify", "clarify", "confirm missing", "stakeholder")):
        return "risk_mitigation"
    return "customer_follow_up"


def _infer_timing_hint(text: str) -> str:
    lowered = text.lower()
    if "today" in lowered:
        return "today"
    if "this week" in lowered or "by friday" in lowered:
        return "this_week"
    if "next week" in lowered:
        return "next_week"
    if "this month" in lowered:
        return "this_month"
    if "this quarter" in lowered:
        return "this_quarter"
    return "unspecified"


def build_task_candidates(
    *,
    meeting_summary: dict[str, Any],
    risk_flags: list[str],
    lead_priority: str,
    opportunity_stage: str,
) -> list[dict[str, Any]]:
    next_steps = _dedupe(_normalize_list(meeting_summary.get("next_steps")))
    confirmed_needs = _normalize_list(meeting_summary.get("confirmed_needs"))
    candidate_texts = list(next_steps)

    for need in confirmed_needs:
        lowered = need.lower()
        if any(token in lowered for token in ("proposal", "quote", "pricing", "security", "integration", "demo")):
            candidate_texts.append(need)

    if "stakeholder_missing" in {flag.lower() for flag in risk_flags}:
        candidate_texts.append("identify missing decision makers")

    candidate_texts = _dedupe(candidate_texts)

    return [
        {
            "text": text,
            "source": "meeting_next_steps" if text in next_steps else "derived_signal",
            "task_type": _infer_task_type(text),
            "priority_hint": lead_priority if lead_priority in {"low", "medium", "high"} else "medium",
            "timing_hint": _infer_timing_hint(text),
            "evidence": [text, f"stage={opportunity_stage}"],
        }
        for text in candidate_texts
    ]


def build_tasks_from_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in candidates:
        text = str(row.get("text", "")).strip()
        if not text:
            continue
        title = text[:1].upper() + text[1:]
        if title.lower().startswith("send tailored proposal"):
            title = "Send tailored proposal"
        if title.lower().startswith("schedule technical deep-dive"):
            title = "Schedule technical deep-dive"
        timing_hint = str(row.get("timing_hint", "unspecified")).strip()
        days = 1 if timing_hint in {"today", "this_week", "unspecified"} else 7
        evidence = "; ".join(str(item) for item in row.get("evidence", []) if str(item).strip())
        output.append(
            {
                "title": title,
                "description": evidence or text,
                "priority": str(row.get("priority_hint", "medium")).strip() or "medium",
                "due_at": (date.today() + timedelta(days=days)).isoformat(),
                "status": "open",
                "owner": "Sales",
            }
        )
    return output
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```powershell
pytest D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_task_candidates.py -q
```

Expected:

- `2 passed`

- [ ] **Step 5: Commit**

```powershell
git -C D:\minimind\.worktrees\minimind-job-agent add `
  sales_copilot/task_candidates.py `
  tests/sales_copilot/test_task_candidates.py
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "feat: add task candidate helpers"
```

### Task 2: Thread task_candidates through prompts and workflow state

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\sales_copilot\state.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\sales_copilot\prompts.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_prompts.py`

- [ ] **Step 1: Write the failing prompt/state tests**

```python
from typing import get_type_hints

from sales_copilot.prompts import build_followup_plan_messages
from sales_copilot.state import SalesCopilotState


def test_sales_copilot_state_includes_task_candidates() -> None:
    hints = get_type_hints(SalesCopilotState)
    assert "task_candidates" in hints


def test_build_followup_plan_messages_mentions_task_candidates_and_prioritizes_them() -> None:
    messages = build_followup_plan_messages(
        meeting_summary={"next_steps": ["send tailored proposal by Friday"]},
        opportunity_stage="proposal",
        risk_flags=["stakeholder_missing"],
        task_candidates=[
            {
                "text": "send tailored proposal by Friday",
                "source": "meeting_next_steps",
                "task_type": "proposal_or_quote",
                "priority_hint": "high",
                "timing_hint": "this_week",
                "evidence": ["Customer asked for proposal by Friday."],
            }
        ],
    )

    prompt_text = messages[1]["content"].lower()
    assert "task candidates" in prompt_text
    assert "prioritize" in prompt_text
    assert "do not ignore the task candidates" in prompt_text
    assert '"text": "send tailored proposal by Friday"' in messages[1]["content"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```powershell
pytest D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_prompts.py -q
```

Expected:

- failures because `task_candidates` is missing from the state and prompt signature/content

- [ ] **Step 3: Write the minimal implementation**

```python
# state.py
task_candidates: list[dict[str, Any]]
```

```python
# prompts.py
def build_followup_plan_messages(
    *,
    meeting_summary: dict,
    opportunity_stage: str,
    risk_flags: list[str],
    task_candidates: list[dict],
) -> list[dict[str, str]]:
    system_prompt = (
        "You are a sales copilot. Create a follow-up plan from the evidence only. "
        "Return valid JSON only. Do not hallucinate."
    )
    user_prompt = (
        "Write a concise follow-up plan in JSON with next actions, owners, timing, "
        "and stage-aware guidance.\n"
        "Prioritize the task candidates below. Do not ignore the task candidates when they already contain concrete follow-up actions. "
        "Only add generic qualification tasks when the task candidates are insufficient.\n\n"
        "Meeting summary:\n"
        f"{json.dumps(meeting_summary, ensure_ascii=False)}\n\n"
        f"Opportunity stage:\n{opportunity_stage}\n\n"
        f"Risk flags:\n{', '.join(risk_flags) if risk_flags else 'None'}\n\n"
        "Task candidates:\n"
        f"{json.dumps(task_candidates, ensure_ascii=False)}"
    )
    return _build_messages(system_prompt, user_prompt)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```powershell
pytest D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_prompts.py -q
```

Expected:

- prompt tests pass with the new `task_candidates` contract

- [ ] **Step 5: Commit**

```powershell
git -C D:\minimind\.worktrees\minimind-job-agent add `
  sales_copilot/state.py `
  sales_copilot/prompts.py `
  tests/sales_copilot/test_prompts.py
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "feat: thread task candidates into prompt contracts"
```

### Task 3: Add workflow node, merge candidate-derived tasks, and verify benchmark impact

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\sales_copilot\graph.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_graph.py`

- [ ] **Step 1: Write the failing graph tests**

```python
from sales_copilot.graph import build_sales_copilot_graph


def test_standard_follow_up_flow_records_build_task_candidates(tmp_path) -> None:
    graph = build_sales_copilot_graph(
        llm_client=_FakeLLMClient(),
        database_path=tmp_path / "sales_copilot.db",
    )

    result = graph.invoke(
        {
            "meeting_summary": {
                "confirmed_needs": ["proposal support"],
                "next_steps": ["send tailored proposal by Friday"],
            },
            "lead_score": 60,
            "lead_priority": "medium",
            "opportunity_stage": "proposal",
            "risk_flags": [],
            "workflow_log": [],
        }
    )

    assert "build_task_candidates" in result["workflow_log"]
    assert result["task_candidates"][0]["text"] == "send tailored proposal by Friday"


def test_standard_follow_up_merges_candidate_tasks_when_model_returns_empty_tasks(tmp_path) -> None:
    class _SparseLLM(_FakeLLMClient):
        def complete(self, messages, response_format=None):
            prompt_text = "\n".join(message["content"] for message in messages)
            if "follow-up plan" in prompt_text.lower():
                return '{"summary": "Execute the agreed follow-up.", "tasks": []}'
            return super().complete(messages, response_format=response_format)

    graph = build_sales_copilot_graph(
        llm_client=_SparseLLM(),
        database_path=tmp_path / "sales_copilot.db",
    )

    result = graph.invoke(
        {
            "meeting_summary": {
                "confirmed_needs": ["proposal support"],
                "next_steps": ["send tailored proposal by Friday"],
            },
            "lead_score": 82,
            "lead_priority": "high",
            "opportunity_stage": "proposal",
            "risk_flags": [],
            "workflow_log": [],
        }
    )

    assert any(task["title"] == "Send tailored proposal" for task in result["task_payload"])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```powershell
pytest D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_graph.py -q
```

Expected:

- failures because the graph has no `build_task_candidates` node and no candidate-task merge

- [ ] **Step 3: Write the minimal implementation**

```python
# graph.py
from sales_copilot.task_candidates import build_task_candidates, build_tasks_from_candidates


def build_task_candidates_node(state: SalesCopilotState, *, llm_client=None, database_path=None) -> dict[str, Any]:
    del llm_client, database_path
    candidates = build_task_candidates(
        meeting_summary=state.get("meeting_summary", {}),
        risk_flags=_normalize_list(state.get("risk_flags")),
        lead_priority=str(state.get("lead_priority", "medium") or "medium"),
        opportunity_stage=str(state.get("opportunity_stage", "discovery") or "discovery"),
    )
    return _step_result(state, "build_task_candidates", {"task_candidates": candidates})


def _merge_task_candidates_into_payload(state: SalesCopilotState, payload: dict[str, Any]) -> dict[str, Any]:
    candidate_tasks = build_tasks_from_candidates(state.get("task_candidates", []))
    payload["tasks"] = _merge_task_payloads(payload.get("tasks", []), candidate_tasks)
    if not str(payload.get("summary", "")).strip() and state.get("task_candidates"):
        payload["summary"] = "; ".join(row["text"] for row in state["task_candidates"][:2])
    return payload


def _build_followup_payload(state: SalesCopilotState, *, llm_client) -> dict[str, Any]:
    messages = build_followup_plan_messages(
        meeting_summary=state.get("meeting_summary", {}),
        opportunity_stage=state.get("opportunity_stage", ""),
        risk_flags=_normalize_list(state.get("risk_flags")),
        task_candidates=state.get("task_candidates", []),
    )
    payload = _parse_json_object(llm_client.complete(messages, response_format={"type": "json_object"}))
    tasks = payload.get("tasks") or payload.get("task_payload") or []
    payload["tasks"] = tasks if isinstance(tasks, list) else []
    payload = _merge_task_candidates_into_payload(state, payload)
    return _augment_follow_up_payload_with_missing_facts(state, payload)
```

And wire the new node:

```python
builder.add_node("build_task_candidates", _bind_node(build_task_candidates_node, ...))
builder.add_edge("load_account_memory", "evaluate_lead")
builder.add_edge("evaluate_lead", "build_task_candidates")
builder.add_conditional_edges("build_task_candidates", route_after_lead_evaluation, {...})
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```powershell
pytest D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_task_candidates.py `
  D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_prompts.py `
  D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_graph.py -q
```

Expected:

- all targeted task-candidate tests pass

- [ ] **Step 5: Run benchmark verification**

Run:

```powershell
$env:DEEPSEEK_API_KEY='YOUR_KEY'
& 'D:\anaconda\envs\minimind_job_agent\python.exe' `
  'D:\minimind\.worktrees\minimind-job-agent\scripts\run_sales_copilot_workflow_quality_eval.py' `
  --cases 'D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_artificial_sales_benchmark_50\artificial_sales_workflow_benchmark_50.jsonl' `
  --database-path 'D:\minimind\.worktrees\minimind-job-agent\data\sales_copilot\sales_copilot.db' `
  --output-dir 'D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_artificial_sales_workflow_quality_baseline_task_candidates'
```

Then compare against:

```text
D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_artificial_sales_workflow_quality_baseline\20260412195951\report.json
```

Primary success checks:

- `task_structure_correctness_avg` improves
- `task_execution_quality_avg` improves
- `overall_score_avg` does not regress materially

- [ ] **Step 6: Commit**

```powershell
git -C D:\minimind\.worktrees\minimind-job-agent add `
  sales_copilot/graph.py `
  tests/sales_copilot/test_graph.py
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "feat: drive follow-up tasks from task candidates"
```
