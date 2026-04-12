# Sales Copilot Artificial Sales Workflow Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a 50-case AI-authored ecommerce sales workflow benchmark with complete parse and workflow expectations, plus a CLI that generates the benchmark and README into the evals tree.

**Architecture:** Add one focused benchmark-authoring module under `evals/sales_copilot` that defines the 50-case blueprint, tool schema, validation helpers, and export helpers. Add a dedicated script under `scripts/` to call DeepSeek case-by-case and write the final JSONL/README without disturbing existing CSDS-derived benchmark builders.

**Tech Stack:** Python, DeepSeek tool-call structured generation, existing Sales Copilot eval helpers, pytest

---

### Task 1: Add benchmark blueprint, validation, and export helpers

**Files:**
- Create: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\artificial_sales_workflow_benchmark.py`
- Test: `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_artificial_sales_workflow_benchmark.py`

- [ ] **Step 1: Write the failing tests**

```python
from evals.sales_copilot.artificial_sales_workflow_benchmark import (
    ARTIFICIAL_ROUTE_TARGETS,
    ARTIFICIAL_PHASE_TARGETS,
    build_sales_case_blueprints,
    validate_authored_case,
    write_artificial_sales_readme,
)


def test_build_sales_case_blueprints_hits_route_and_phase_targets() -> None:
    blueprints = build_sales_case_blueprints()

    route_counts: dict[str, int] = {}
    phase_counts: dict[str, int] = {}
    for row in blueprints:
        route = row["target_route"]
        phase = row["funnel_phase"]
        route_counts[route] = route_counts.get(route, 0) + 1
        phase_counts[phase] = phase_counts.get(phase, 0) + 1

    assert len(blueprints) == 50
    assert route_counts == ARTIFICIAL_ROUTE_TARGETS
    assert phase_counts == ARTIFICIAL_PHASE_TARGETS


def test_validate_authored_case_requires_expected_workflow_shape() -> None:
    row = {
        "case_id": "artificial_sales_001",
        "segment": "artificial_sales_workflow_benchmark",
        "source_case_type": "merchant_onboarding",
        "customer_profile_text": "Merchant profile",
        "meeting_note_text": "Meeting note",
        "expected_parse": {
            "account_name": "Merchant A",
            "customer_roles": ["AE", "merchant_ops"],
            "confirmed_needs": ["crm integration"],
            "objections": [],
            "next_steps": ["schedule demo"],
            "budget_signals": ["budget approved"],
            "timeline_signals": ["this month"],
            "competitors": [],
        },
        "expected_workflow": {
            "lead_score_range": [80, 90],
            "lead_priority": "high",
            "opportunity_stage": "proposal",
            "expected_route": "high_priority_follow_up",
            "expected_crm_writeback": {
                "should_write": True,
                "account_status": "qualified_opportunity",
                "opportunity_stage": "proposal",
                "risk_flags": ["integration_scope_open"],
                "recommended_next_step": "send proposal and confirm demo stakeholders",
                "evidence": ["merchant asked for proposal"],
                "acceptable_variants": ["share proposal deck"],
            },
            "expected_task_bundle": {
                "should_generate": True,
                "tasks": [
                    {
                        "title": "Send proposal",
                        "description": "Send proposal and confirm attendees.",
                        "priority": "high",
                        "owner": "Sales",
                        "timing_expectation": "next_day",
                        "evidence": ["proposal requested"],
                    }
                ],
                "acceptable_variants": ["share proposal pack"],
            },
        },
        "author_note": "Test note",
    }

    validate_authored_case(row)


def test_write_artificial_sales_readme_includes_route_distribution(tmp_path) -> None:
    rows = [
        {"funnel_phase": "initial_contact", "expected_workflow": {"expected_route": "high_priority_follow_up"}},
        {"funnel_phase": "nurture", "expected_workflow": {"expected_route": "low_priority_nurture"}},
    ]
    path = tmp_path / "README.md"
    write_artificial_sales_readme(path, rows)

    content = path.read_text(encoding="utf-8")
    assert "Artificial Sales Workflow Benchmark 50" in content
    assert "`high_priority_follow_up`: 1" in content
    assert "`low_priority_nurture`: 1" in content
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```powershell
pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_artificial_sales_workflow_benchmark.py -q
```

Expected:

- collection succeeds
- failure because `artificial_sales_workflow_benchmark.py` does not exist yet

- [ ] **Step 3: Write the minimal implementation**

```python
from __future__ import annotations

import json
from pathlib import Path


ARTIFICIAL_ROUTE_TARGETS = {
    "high_priority_follow_up": 15,
    "standard_follow_up": 15,
    "need_more_info": 10,
    "low_priority_nurture": 10,
}

ARTIFICIAL_PHASE_TARGETS = {
    "initial_contact": 10,
    "discovery_qualification": 10,
    "evaluation_objection": 10,
    "commercial_progression": 10,
    "nurture_deferred": 10,
}


def build_sales_case_blueprints() -> list[dict[str, str]]:
    blueprints: list[dict[str, str]] = []
    route_slots = (
        ["high_priority_follow_up"] * 15
        + ["standard_follow_up"] * 15
        + ["need_more_info"] * 10
        + ["low_priority_nurture"] * 10
    )
    phase_slots = (
        ["initial_contact"] * 10
        + ["discovery_qualification"] * 10
        + ["evaluation_objection"] * 10
        + ["commercial_progression"] * 10
        + ["nurture_deferred"] * 10
    )
    scenario_types = [
        "merchant_onboarding",
        "crm_integration",
        "private_deployment",
        "team_collaboration",
        "reporting_analytics",
        "campaign_operations",
        "budget_pushback",
        "implementation_effort",
        "security_review",
        "stalled_follow_up",
    ]
    for index in range(50):
        blueprints.append(
            {
                "case_id": f"artificial_sales_{index + 1:03d}",
                "segment": "artificial_sales_workflow_benchmark",
                "target_route": route_slots[index],
                "funnel_phase": phase_slots[index],
                "source_case_type": scenario_types[index % len(scenario_types)],
            }
        )
    return blueprints


def validate_authored_case(row: dict[str, object]) -> None:
    for field in ("case_id", "segment", "source_case_type", "customer_profile_text", "meeting_note_text", "expected_parse", "expected_workflow", "author_note"):
        if field not in row:
            raise ValueError(f"Missing required field: {field}")
    workflow = row["expected_workflow"]
    if not isinstance(workflow, dict):
        raise ValueError("expected_workflow must be a dict")
    for field in ("lead_score_range", "lead_priority", "opportunity_stage", "expected_route", "expected_crm_writeback", "expected_task_bundle"):
        if field not in workflow:
            raise ValueError(f"Missing expected_workflow field: {field}")


def write_artificial_sales_readme(path: Path, rows: list[dict[str, object]]) -> None:
    route_counts: dict[str, int] = {}
    phase_counts: dict[str, int] = {}
    for row in rows:
        workflow = row.get("expected_workflow", {})
        if isinstance(workflow, dict):
            route = str(workflow.get("expected_route", "unknown"))
            route_counts[route] = route_counts.get(route, 0) + 1
        phase = str(row.get("funnel_phase", "unknown"))
        phase_counts[phase] = phase_counts.get(phase, 0) + 1
    content = [
        "# Artificial Sales Workflow Benchmark 50",
        "",
        "AI-authored ecommerce merchant/platform sales workflow benchmark draft.",
        "",
        "## Route distribution",
        "",
    ]
    for route, count in sorted(route_counts.items()):
        content.append(f"- `{route}`: {count}")
    content.extend(["", "## Funnel distribution", ""])
    for phase, count in sorted(phase_counts.items()):
        content.append(f"- `{phase}`: {count}")
    Path(path).write_text("\n".join(content) + "\n", encoding="utf-8")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```powershell
pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_artificial_sales_workflow_benchmark.py -q
```

Expected:

- `3 passed`

- [ ] **Step 5: Commit**

```powershell
git -C D:\minimind\.worktrees\minimind-job-agent add `
  evals/sales_copilot/artificial_sales_workflow_benchmark.py `
  tests/evals/test_artificial_sales_workflow_benchmark.py
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "feat: add artificial sales benchmark helpers"
```

### Task 2: Add LLM authoring helpers and benchmark export script

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\artificial_sales_workflow_benchmark.py`
- Create: `D:\minimind\.worktrees\minimind-job-agent\scripts\build_artificial_sales_workflow_benchmark.py`
- Test: `D:\minimind\.worktrees\minimind-job-agent\tests\scripts\test_build_artificial_sales_workflow_benchmark.py`

- [ ] **Step 1: Write the failing CLI test**

```python
from pathlib import Path

from scripts import build_artificial_sales_workflow_benchmark


def test_build_artificial_sales_workflow_benchmark_cli_writes_outputs(monkeypatch, tmp_path: Path) -> None:
    class _FakeClient:
        def complete_with_tool(self, messages, tools, tool_choice):
            return {
                "tool_name": "submit_artificial_sales_workflow_case",
                "arguments": {
                    "customer_profile_text": "Merchant profile",
                    "meeting_note_text": "Merchant asked for CRM integration demo next week.",
                    "expected_parse": {
                        "account_name": "Merchant A",
                        "customer_roles": ["ae", "ops_manager"],
                        "confirmed_needs": ["crm integration"],
                        "objections": [],
                        "next_steps": ["schedule demo"],
                        "budget_signals": ["budget available"],
                        "timeline_signals": ["next week"],
                        "competitors": [],
                    },
                    "expected_workflow": {
                        "lead_score_range": [78, 88],
                        "lead_priority": "high",
                        "opportunity_stage": "qualification",
                        "expected_route": "high_priority_follow_up",
                        "expected_crm_writeback": {
                            "should_write": True,
                            "account_status": "qualified_opportunity",
                            "opportunity_stage": "qualification",
                            "risk_flags": ["demo_pending"],
                            "recommended_next_step": "schedule demo and confirm integration stakeholders",
                            "evidence": ["merchant requested crm integration demo"],
                            "acceptable_variants": ["book demo and confirm stakeholders"],
                        },
                        "expected_task_bundle": {
                            "should_generate": True,
                            "tasks": [
                                {
                                    "title": "Schedule integration demo",
                                    "description": "Book demo and confirm stakeholders.",
                                    "priority": "high",
                                    "owner": "Sales",
                                    "timing_expectation": "next_day",
                                    "evidence": ["demo requested"],
                                }
                            ],
                            "acceptable_variants": ["book integration demo"],
                        },
                    },
                    "author_note": "AI-authored draft",
                },
            }

    monkeypatch.setattr(build_artificial_sales_workflow_benchmark, "_build_deepseek_client", lambda api_key, base_url, model: _FakeClient())
    monkeypatch.setattr(
        "sys.argv",
        [
            "build_artificial_sales_workflow_benchmark.py",
            "--api-key",
            "test-key",
            "--output-dir",
            str(tmp_path / "outputs"),
            "--limit",
            "2",
        ],
    )

    assert build_artificial_sales_workflow_benchmark.main() == 0
    assert (tmp_path / "outputs" / "artificial_sales_workflow_benchmark_50.jsonl").exists()
    assert (tmp_path / "outputs" / "artificial_sales_workflow_benchmark_50_README.md").exists()
```

- [ ] **Step 2: Run the CLI test to verify it fails**

Run:

```powershell
pytest D:\minimind\.worktrees\minimind-job-agent\tests\scripts\test_build_artificial_sales_workflow_benchmark.py -q
```

Expected:

- failure because the new script and tool schema do not exist yet

- [ ] **Step 3: Add authoring messages, tool schema, and CLI**

```python
ARTIFICIAL_SALES_TOOL_NAME = "submit_artificial_sales_workflow_case"


def build_artificial_sales_tools() -> list[dict[str, object]]:
    return [
        {
            "type": "function",
            "function": {
                "name": ARTIFICIAL_SALES_TOOL_NAME,
                "description": "Return one authored ecommerce sales workflow benchmark case.",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_profile_text": {"type": "string"},
                        "meeting_note_text": {"type": "string"},
                        "expected_parse": {"type": "object"},
                        "expected_workflow": {"type": "object"},
                        "author_note": {"type": "string"},
                    },
                    "required": [
                        "customer_profile_text",
                        "meeting_note_text",
                        "expected_parse",
                        "expected_workflow",
                        "author_note",
                    ],
                    "additionalProperties": False,
                },
            },
        }
    ]


def build_artificial_sales_messages(blueprint: dict[str, str]) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are authoring an ecommerce merchant/platform sales workflow benchmark case. "
                "Return one realistic case through the tool only. Keep it grounded, varied, and operationally plausible."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(blueprint, ensure_ascii=False),
        },
    ]


def author_sales_case(blueprint: dict[str, str], *, llm_client: object) -> dict[str, object]:
    tool_result = llm_client.complete_with_tool(
        build_artificial_sales_messages(blueprint),
        tools=build_artificial_sales_tools(),
        tool_choice={"type": "function", "function": {"name": ARTIFICIAL_SALES_TOOL_NAME}},
    )
    row = dict(blueprint)
    row.update(tool_result["arguments"])
    validate_authored_case(row)
    return row
```

```python
import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evals.sales_copilot.artificial_sales_workflow_benchmark import (
    build_sales_case_blueprints,
    author_sales_case,
    write_artificial_sales_readme,
)
from evals.sales_copilot.workflow_calibrated_benchmark import write_jsonl
from llm.deepseek_client import DeepSeekClient


def _build_deepseek_client(api_key: str, base_url: str, model: str):
    return DeepSeekClient(api_key=api_key, base_url=base_url, model=model)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--api-key", default="")
    parser.add_argument("--api-base-url", default=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
    parser.add_argument("--api-model", default=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"))
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    api_key = str(args.api_key or os.environ.get("DEEPSEEK_API_KEY", "")).strip()
    if not api_key:
        raise SystemExit("Missing DeepSeek API key. Pass --api-key or set DEEPSEEK_API_KEY.")

    client = _build_deepseek_client(api_key, args.api_base_url, args.api_model)
    rows = []
    for blueprint in build_sales_case_blueprints()[: args.limit]:
        rows.append(author_sales_case(blueprint, llm_client=client))

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / "artificial_sales_workflow_benchmark_50.jsonl"
    readme_path = output_dir / "artificial_sales_workflow_benchmark_50_README.md"
    write_jsonl(jsonl_path, rows)
    write_artificial_sales_readme(readme_path, rows)
    print(f"Built {len(rows)} artificial sales workflow benchmark rows.")
    return 0
```

- [ ] **Step 4: Run the CLI test to verify it passes**

Run:

```powershell
pytest D:\minimind\.worktrees\minimind-job-agent\tests\scripts\test_build_artificial_sales_workflow_benchmark.py -q
```

Expected:

- `1 passed`

- [ ] **Step 5: Commit**

```powershell
git -C D:\minimind\.worktrees\minimind-job-agent add `
  evals/sales_copilot/artificial_sales_workflow_benchmark.py `
  scripts/build_artificial_sales_workflow_benchmark.py `
  tests/scripts/test_build_artificial_sales_workflow_benchmark.py
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "feat: add artificial sales benchmark builder"
```

### Task 3: Verify end-to-end generation and document the artifact

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\docs\sales-copilot-retrospective.md`
- Output: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_artificial_sales_benchmark_50\artificial_sales_workflow_benchmark_50.jsonl`
- Output: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_artificial_sales_benchmark_50\artificial_sales_workflow_benchmark_50_README.md`

- [ ] **Step 1: Run the focused test suite**

Run:

```powershell
pytest `
  D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_artificial_sales_workflow_benchmark.py `
  D:\minimind\.worktrees\minimind-job-agent\tests\scripts\test_build_artificial_sales_workflow_benchmark.py -q
```

Expected:

- all targeted tests pass

- [ ] **Step 2: Run evals regression tests**

Run:

```powershell
pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals -q
```

Expected:

- eval tests remain green

- [ ] **Step 3: Generate the first benchmark draft**

Run:

```powershell
$env:DEEPSEEK_API_KEY=\"<set in environment>\"\n& 'D:\anaconda\envs\minimind_job_agent\python.exe' `
  'D:\minimind\.worktrees\minimind-job-agent\scripts\build_artificial_sales_workflow_benchmark.py' `
  --output-dir 'D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_artificial_sales_benchmark_50'
```

Expected:

- command prints `Built 50 artificial sales workflow benchmark rows.`
- JSONL and README appear in the output directory

- [ ] **Step 4: Add a short retrospective note**

```markdown
## Artificial Sales Workflow Benchmark

We added an AI-authored 50-case sales workflow benchmark to cover ecommerce merchant and platform sales scenarios that are not represented well in CSDS-derived datasets. This benchmark is intended for workflow-level evaluation, especially route, CRM writeback, task generation, and future RAG A/B comparisons on actual sales-style cases.
```

- [ ] **Step 5: Run syntax verification and commit**

Run:

```powershell
@'\nimport py_compile\npy_compile.compile(r\"D:\\minimind\\.worktrees\\minimind-job-agent\\evals\\sales_copilot\\artificial_sales_workflow_benchmark.py\", doraise=True)\npy_compile.compile(r\"D:\\minimind\\.worktrees\\minimind-job-agent\\scripts\\build_artificial_sales_workflow_benchmark.py\", doraise=True)\nprint(\"py_compile ok\")\n'@ | python -
```

Then commit:

```powershell
git -C D:\minimind\.worktrees\minimind-job-agent add `
  docs/sales-copilot-retrospective.md `
  evals/sales_copilot/outputs_artificial_sales_benchmark_50 `
  docs/superpowers/specs/2026-04-12-sales-copilot-artificial-sales-workflow-benchmark-design.md `
  docs/superpowers/plans/2026-04-12-sales-copilot-artificial-sales-workflow-benchmark.md
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "feat: add artificial sales workflow benchmark draft"
```
