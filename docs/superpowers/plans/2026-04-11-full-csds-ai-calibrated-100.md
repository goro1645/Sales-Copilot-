# Full-CSDS AI-Calibrated-100 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fill the `100`-case calibrated working set with AI-authored final review blocks and export a standalone `full_csds_ai_calibrated_100.jsonl` benchmark draft.

**Architecture:** Reuse the existing calibrated-subset pipeline, add a DeepSeek tool-call calibration pass that reads each working-row context and writes `human_review.final_expected_parse`, then export the final benchmark from those AI-completed review blocks. Preserve the original working set and keep provenance explicit by marking the review metadata as AI-authored.

**Tech Stack:** Python, DeepSeek API, JSONL tooling, pytest

---

### Task 1: Add failing coverage for AI review fill and AI export

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_calibrated_subset.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\tests\scripts\test_build_full_csds_calibrated_subset.py`

- [ ] **Step 1: Write failing unit tests for row-level AI review filling**

```python
class _FakeClient:
    def complete_with_tool(self, messages, tools, tool_choice):
        return {
            "tool_name": "submit_ai_calibrated_parse",
            "arguments": {
                "corrected_expected_parse": {
                    "confirmed_needs": ["confirm refund progress"],
                    "budget_signals": ["coupon cannot be reused"],
                    "timeline_signals": ["within one business day"],
                    "next_steps": ["customer submits after-sales request"],
                }
            },
        }


def test_fill_ai_review_rows_writes_human_review_block() -> None:
    rows = [{
        "case_id": "case_1",
        "sampling_bucket": "budget_boundary",
        "meeting_note_text": "Customer asks about coupon reuse and refund timing.",
        "user_summ": ["check coupon reuse"],
        "agent_summ": ["submit after-sales request within one business day"],
        "final_summ": ["coupon cannot be reused; submit after-sales request within one business day"],
        "auto_expected_parse": {
            "account_name": "JD Support",
            "customer_roles": ["user", "agent"],
            "confirmed_needs": ["check coupon reuse"],
            "budget_signals": [],
            "timeline_signals": [],
            "next_steps": ["submit after-sales request"],
            "competitors": [],
        },
        "baseline_parse_result": {
            "account_name": "JD Support",
            "customer_roles": ["user", "agent"],
            "confirmed_needs": ["check coupon reuse"],
            "budget_signals": ["coupon cannot be reused"],
            "timeline_signals": ["within one business day"],
            "next_steps": ["submit after-sales request"],
            "competitors": [],
        },
        "pre_annotation": {
            "corrected_expected_parse": {
                "confirmed_needs": ["check coupon reuse"],
                "budget_signals": ["coupon cannot be reused"],
                "timeline_signals": [],
                "next_steps": ["submit after-sales request"],
            },
            "review_reason": "budget_boundary_case",
        },
        "human_review": {},
    }]

    reviewed = fill_ai_review_rows(rows, llm_client=_FakeClient())

    assert reviewed[0]["human_review"]["reviewed_by"] == "ai"
    assert reviewed[0]["human_review"]["review_status"] == "completed"
    assert reviewed[0]["human_review"]["final_expected_parse"]["timeline_signals"] == ["within one business day"]
```

- [ ] **Step 2: Run targeted tests to confirm they fail first**

Run:

```powershell
pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_calibrated_subset.py D:\minimind\.worktrees\minimind-job-agent\tests\scripts\test_build_full_csds_calibrated_subset.py -q
```

Expected: FAIL with missing `fill_ai_review_rows` / missing AI export CLI behavior.

- [ ] **Step 3: Add failing CLI test for AI fill + AI export mode**

```python
def test_build_full_csds_calibrated_subset_cli_fills_ai_review_and_exports(monkeypatch, tmp_path: Path) -> None:
    working_path = tmp_path / "working.jsonl"
    working_path.write_text(
        '{"case_id":"case_1","source_uid":"1","source_split":"test","sampling_bucket":"ordinary_stable",'
        '"meeting_note_text":"m","customer_profile_text":"c","user_summ":[],"agent_summ":[],"final_summ":[],'
        '"auto_expected_parse":{"account_name":"JD Support","customer_roles":["user","agent"],'
        '"confirmed_needs":["need"],"budget_signals":[],"timeline_signals":[],"next_steps":["follow up"],"competitors":[]},'
        '"baseline_parse_result":{"account_name":"JD Support","customer_roles":["user","agent"],'
        '"confirmed_needs":["need"],"budget_signals":[],"timeline_signals":[],"next_steps":["follow up"],"competitors":[]},'
        '"pre_annotation":{"corrected_expected_parse":{"confirmed_needs":["need"],"budget_signals":[],"timeline_signals":[],"next_steps":["follow up"]},'
        '"review_reason":"auto_gold_vs_baseline_alignment"},'
        '"human_review":{}}\n',
        encoding="utf-8",
    )

    class _FakeClient:
        def complete_with_tool(self, messages, tools, tool_choice):
            return {
                "tool_name": "submit_ai_calibrated_parse",
                "arguments": {
                    "corrected_expected_parse": {
                        "confirmed_needs": ["need"],
                        "budget_signals": [],
                        "timeline_signals": [],
                        "next_steps": ["contact support"],
                    }
                },
            }

    monkeypatch.setattr(
        build_full_csds_calibrated_subset,
        "_build_deepseek_client",
        lambda api_key, base_url, model: _FakeClient(),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "build_full_csds_calibrated_subset.py",
            "--fill-ai-review-from-working",
            str(working_path),
            "--api-key",
            "test-key",
            "--output-dir",
            str(tmp_path / "outputs"),
        ],
    )

    assert build_full_csds_calibrated_subset.main() == 0
    assert (tmp_path / "outputs" / "full_csds_calibration_working_100.ai_reviewed.jsonl").exists()
    assert (tmp_path / "outputs" / "full_csds_ai_calibrated_100.jsonl").exists()
```

- [ ] **Step 4: Run targeted tests again and keep the failure output**

Run:

```powershell
pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_calibrated_subset.py D:\minimind\.worktrees\minimind-job-agent\tests\scripts\test_build_full_csds_calibrated_subset.py -q
```

Expected: FAIL with missing CLI flags and missing helper implementation.

- [ ] **Step 5: Commit the red tests**

```powershell
git -C D:\minimind\.worktrees\minimind-job-agent add D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_calibrated_subset.py D:\minimind\.worktrees\minimind-job-agent\tests\scripts\test_build_full_csds_calibrated_subset.py
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "test: cover ai calibrated subset flow"
```

---

### Task 2: Implement AI review filling helpers in calibrated subset module

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\calibrated_subset.py`
- Test: `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_calibrated_subset.py`

- [ ] **Step 1: Add tool schema and prompt-building helpers**

```python
AI_REVIEW_FIELDS = (
    "confirmed_needs",
    "budget_signals",
    "timeline_signals",
    "next_steps",
)


def build_ai_calibration_tools() -> list[dict[str, Any]]:
    return [{
        "type": "function",
        "function": {
            "name": "submit_ai_calibrated_parse",
            "description": "Return the final AI-calibrated expected_parse for the target fields.",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "corrected_expected_parse": {
                        "type": "object",
                        "properties": {
                            field: {"type": "array", "items": {"type": "string"}}
                            for field in AI_REVIEW_FIELDS
                        },
                        "required": list(AI_REVIEW_FIELDS),
                        "additionalProperties": False,
                    }
                },
                "required": ["corrected_expected_parse"],
                "additionalProperties": False,
            },
        },
    }]
```

- [ ] **Step 2: Add row-level AI review fill helper**

```python
def fill_ai_review_for_row(
    row: dict[str, Any],
    *,
    llm_client: Any,
) -> dict[str, Any]:
    tool_result = llm_client.complete_with_tool(
        build_ai_calibration_messages(row),
        tools=build_ai_calibration_tools(),
        tool_choice={"type": "function", "function": {"name": "submit_ai_calibrated_parse"}},
    )
    arguments = tool_result["arguments"]
    corrected = _normalize_ai_corrected_expected_parse(arguments.get("corrected_expected_parse", {}), row)
    updated = dict(row)
    updated["human_review"] = {
        "final_expected_parse": corrected,
        "reviewed_by": "ai",
        "review_status": "completed",
        "review_note": "AI-calibrated draft produced with DeepSeek tool-call review.",
    }
    return updated
```

- [ ] **Step 3: Add batch helper and export naming helpers**

```python
def fill_ai_review_rows(
    rows: list[dict[str, Any]],
    *,
    llm_client: Any,
) -> list[dict[str, Any]]:
    return [fill_ai_review_for_row(row, llm_client=llm_client) for row in rows]
```

- [ ] **Step 4: Run the targeted tests and make them pass**

Run:

```powershell
pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_calibrated_subset.py -q
```

Expected: PASS

- [ ] **Step 5: Commit the helper implementation**

```powershell
git -C D:\minimind\.worktrees\minimind-job-agent add D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\calibrated_subset.py D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_calibrated_subset.py
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "feat: add ai calibrated subset helpers"
```

---

### Task 3: Wire AI fill mode into the CLI and document provenance

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\scripts\build_full_csds_calibrated_subset.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\README.md`
- Test: `D:\minimind\.worktrees\minimind-job-agent\tests\scripts\test_build_full_csds_calibrated_subset.py`

- [ ] **Step 1: Add CLI flags and DeepSeek client construction**

```python
parser.add_argument("--fill-ai-review-from-working", default="")
parser.add_argument("--api-key", default="")
parser.add_argument("--api-base-url", default="https://api.deepseek.com")
parser.add_argument("--api-model", default="deepseek-chat")


def _build_deepseek_client(api_key: str, base_url: str, model: str):
    return DeepSeekClient(api_key=api_key, base_url=base_url, model=model)
```

- [ ] **Step 2: Implement the AI fill branch**

```python
if args.fill_ai_review_from_working:
    api_key = args.api_key or os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("Missing DeepSeek API key. Pass --api-key or set DEEPSEEK_API_KEY.")

    working_rows = _read_jsonl_rows(Path(args.fill_ai_review_from_working))
    client = _build_deepseek_client(api_key, args.api_base_url, args.api_model)
    reviewed_rows = fill_ai_review_rows(working_rows, llm_client=client)
    reviewed_path = output_dir / "full_csds_calibration_working_100.ai_reviewed.jsonl"
    final_rows = export_final_calibrated_rows(reviewed_rows)
    final_path = output_dir / "full_csds_ai_calibrated_100.jsonl"
    write_jsonl(reviewed_path, reviewed_rows)
    write_jsonl(final_path, final_rows)
    print(f"AI-reviewed {len(reviewed_rows)} rows.")
    print(f"ai_reviewed_jsonl: {reviewed_path}")
    print(f"final_jsonl: {final_path}")
    return 0
```

- [ ] **Step 3: Document the new AI-calibrated output flow**

```markdown
### Full-CSDS AI-Calibrated-100

The repository can also turn the `100`-case working set into an `AI-calibrated benchmark draft`.

This path:

- keeps the original working set intact
- fills `human_review.final_expected_parse` with an AI-authored review block
- exports `full_csds_ai_calibrated_100.jsonl`
- should be described as `AI-calibrated`, not `human-calibrated`
```

- [ ] **Step 4: Run CLI tests and focused regressions**

Run:

```powershell
pytest D:\minimind\.worktrees\minimind-job-agent\tests\scripts\test_build_full_csds_calibrated_subset.py D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_calibrated_subset.py -q
```

Expected: PASS

- [ ] **Step 5: Commit the CLI/doc wiring**

```powershell
git -C D:\minimind\.worktrees\minimind-job-agent add D:\minimind\.worktrees\minimind-job-agent\scripts\build_full_csds_calibrated_subset.py D:\minimind\.worktrees\minimind-job-agent\README.md D:\minimind\.worktrees\minimind-job-agent\tests\scripts\test_build_full_csds_calibrated_subset.py
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "feat: add ai calibrated subset export flow"
```

---

### Task 4: Verify end-to-end and generate the benchmark draft

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_csds_calibrated_100\full_csds_calibration_working_100.ai_reviewed.jsonl` (generated)
- Modify: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_csds_calibrated_100\full_csds_ai_calibrated_100.jsonl` (generated)

- [ ] **Step 1: Run the relevant regression suite**

Run:

```powershell
pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals D:\minimind\.worktrees\minimind-job-agent\tests\scripts\test_build_full_csds_calibrated_subset.py -q
```

Expected: PASS

- [ ] **Step 2: Run syntax verification**

Run:

```powershell
python -m py_compile D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\calibrated_subset.py D:\minimind\.worktrees\minimind-job-agent\scripts\build_full_csds_calibrated_subset.py
```

Expected: no output

- [ ] **Step 3: Generate the real AI-calibrated benchmark draft**

Run:

```powershell
& 'D:\anaconda\envs\minimind_job_agent\python.exe' 'D:\minimind\.worktrees\minimind-job-agent\scripts\build_full_csds_calibrated_subset.py' `
  --fill-ai-review-from-working 'D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_csds_calibrated_100\full_csds_calibration_working_100.jsonl' `
  --output-dir 'D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_csds_calibrated_100'
```

Expected: prints reviewed row count plus both output paths. Requires `DEEPSEEK_API_KEY` or `--api-key`.

- [ ] **Step 4: Spot-check the generated files**

Run:

```powershell
Get-Content -Path 'D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_csds_calibrated_100\full_csds_calibration_working_100.ai_reviewed.jsonl' -TotalCount 2
Get-Content -Path 'D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_csds_calibrated_100\full_csds_ai_calibrated_100.jsonl' -TotalCount 2
```

Expected: `human_review.reviewed_by = "ai"` present in the reviewed working file and `expected_parse` populated in the exported final file.

- [ ] **Step 5: Commit the implementation**

```powershell
git -C D:\minimind\.worktrees\minimind-job-agent add D:\minimind\.worktrees\minimind-job-agent\docs\superpowers\plans\2026-04-11-full-csds-ai-calibrated-100.md D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\calibrated_subset.py D:\minimind\.worktrees\minimind-job-agent\scripts\build_full_csds_calibrated_subset.py D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_calibrated_subset.py D:\minimind\.worktrees\minimind-job-agent\tests\scripts\test_build_full_csds_calibrated_subset.py D:\minimind\.worktrees\minimind-job-agent\README.md
git -C D:\minimind\.worktrees\minimind-job-agent commit -m "feat: generate ai calibrated csds subset"
```
