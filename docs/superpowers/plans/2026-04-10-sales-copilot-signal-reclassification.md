# Sales Copilot Signal Reclassification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a DeepSeek-powered second-pass signal reclassification layer for `budget_signals`, `timeline_signals`, and `next_steps` in the `CSDS` parse-only evaluation pipeline.

**Architecture:** Keep the current first-pass parse unchanged. Extract weak-field candidates from the first-pass result, send them through a constrained DeepSeek classification prompt, apply a tiny high-precision fallback only for low-confidence or empty-field cases, then project the corrected fields back into the final parse result for evaluation. The feature ships behind an explicit eval flag so baseline vs reclassification runs are comparable.

**Tech Stack:** Python, DeepSeek API, existing Sales Copilot eval pipeline, pytest

---

## File Map

- Create: `D:/minimind/.worktrees/minimind-job-agent/evals/sales_copilot/signal_reclassifier.py`
  - candidate extraction
  - DeepSeek second-pass classification helpers
  - lightweight fallback
  - final field projection
- Modify: `D:/minimind/.worktrees/minimind-job-agent/sales_copilot/prompts.py`
  - add second-pass reclassification prompt builder
- Modify: `D:/minimind/.worktrees/minimind-job-agent/evals/sales_copilot/csds_runner.py`
  - add `use_signal_reclassification` execution path
- Modify: `D:/minimind/.worktrees/minimind-job-agent/scripts/run_sales_copilot_eval.py`
  - expose CLI flag for the new mode
- Modify: `D:/minimind/.worktrees/minimind-job-agent/README.md`
  - document the eval flag and what it changes
- Test: `D:/minimind/.worktrees/minimind-job-agent/tests/evals/test_signal_reclassifier.py`
- Test: `D:/minimind/.worktrees/minimind-job-agent/tests/evals/test_csds_runner.py`

### Task 1: Add reclassification prompt builder

**Files:**
- Modify: `D:/minimind/.worktrees/minimind-job-agent/sales_copilot/prompts.py`
- Test: `D:/minimind/.worktrees/minimind-job-agent/tests/sales_copilot/test_prompts.py`

- [ ] **Step 1: Write the failing test**

```python
def test_build_signal_reclassification_messages_contains_fixed_labels():
    messages = build_signal_reclassification_messages(
        conversation_context="客服说明订单完成后帮助修改",
        signal_candidates=[
            {
                "candidate_id": "sig_001",
                "text": "订单完成后帮助用户完成修改",
                "speaker": "agent",
                "evidence": "用户可以留下信息，在订单完成后帮助用户完成修改",
            }
        ],
    )

    assert messages[0]["role"] == "system"
    assert "budget_signals" in messages[0]["content"]
    assert "timeline_signals" in messages[0]["content"]
    assert "next_steps" in messages[0]["content"]
    assert "\"candidate_id\": \"sig_001\"" in messages[1]["content"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_prompts.py::test_build_signal_reclassification_messages_contains_fixed_labels -q
```

Expected: FAIL because `build_signal_reclassification_messages` does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
def build_signal_reclassification_messages(*, conversation_context: str, signal_candidates: list[dict]) -> list[dict[str, str]]:
    system_prompt = (
        "You classify signal candidates into fixed labels only. "
        "Return valid JSON only. Allowed labels: "
        "budget_signals, timeline_signals, next_steps, other."
    )
    user_prompt = json.dumps(
        {
            "task": "classify_signal_candidates",
            "conversation_context": conversation_context,
            "signal_candidates": signal_candidates,
        },
        ensure_ascii=False,
    )
    return _build_messages(system_prompt, user_prompt)
```

- [ ] **Step 4: Run test to verify it passes**

Run the same pytest command and expect PASS.

- [ ] **Step 5: Commit**

```bash
git add D:/minimind/.worktrees/minimind-job-agent/sales_copilot/prompts.py D:/minimind/.worktrees/minimind-job-agent/tests/sales_copilot/test_prompts.py
git commit -m "feat: add signal reclassification prompt builder"
```

### Task 2: Build candidate extraction and projection helpers

**Files:**
- Create: `D:/minimind/.worktrees/minimind-job-agent/evals/sales_copilot/signal_reclassifier.py`
- Test: `D:/minimind/.worktrees/minimind-job-agent/tests/evals/test_signal_reclassifier.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_extract_signal_candidates_collects_weak_fields_and_objections():
    parse_result = {
        "budget_signals": ["不能再使用优惠券"],
        "timeline_signals": ["订单完成后"],
        "next_steps": ["留下信息"],
        "objections": ["当前无法直接修改"],
    }
    candidates = extract_signal_candidates(parse_result)
    assert [row["text"] for row in candidates] == [
        "不能再使用优惠券",
        "订单完成后",
        "留下信息",
        "当前无法直接修改",
    ]


def test_project_classified_signals_rebuilds_target_fields():
    parse_result = {
        "budget_signals": [],
        "timeline_signals": [],
        "next_steps": [],
    }
    classified = [
        {"candidate_id": "sig_001", "text": "优惠券不能使用", "predicted_label": "budget_signals", "confidence": 0.9, "alternative_labels": []},
        {"candidate_id": "sig_002", "text": "订单完成后", "predicted_label": "timeline_signals", "confidence": 0.9, "alternative_labels": []},
        {"candidate_id": "sig_003", "text": "留下信息", "predicted_label": "next_steps", "confidence": 0.9, "alternative_labels": []},
    ]
    result = project_reclassified_parse_result(parse_result, classified)
    assert result["budget_signals"] == ["优惠券不能使用"]
    assert result["timeline_signals"] == ["订单完成后"]
    assert result["next_steps"] == ["留下信息"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_signal_reclassifier.py -q
```

Expected: FAIL because the helper module does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
TARGET_FIELDS = ("budget_signals", "timeline_signals", "next_steps")


def extract_signal_candidates(parse_result: dict[str, object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    index = 1
    for field in TARGET_FIELDS + ("objections",):
        for value in parse_result.get(field, []) or []:
            if not isinstance(value, str) or not value.strip():
                continue
            rows.append(
                {
                    "candidate_id": f"sig_{index:03d}",
                    "text": value.strip(),
                    "speaker": "agent",
                    "evidence": value.strip(),
                    "normalized_text": value.strip(),
                    "hints": [],
                }
            )
            index += 1
    return rows


def project_reclassified_parse_result(parse_result: dict[str, object], classified_signals: list[dict[str, object]]) -> dict[str, object]:
    result = dict(parse_result)
    for field in TARGET_FIELDS:
        result[field] = []
    for row in classified_signals:
        label = row.get("predicted_label")
        text = row.get("text")
        if label in TARGET_FIELDS and isinstance(text, str) and text.strip():
            result[label].append(text.strip())
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run the same pytest command and expect PASS.

- [ ] **Step 5: Commit**

```bash
git add D:/minimind/.worktrees/minimind-job-agent/evals/sales_copilot/signal_reclassifier.py D:/minimind/.worktrees/minimind-job-agent/tests/evals/test_signal_reclassifier.py
git commit -m "feat: add signal candidate extraction helpers"
```

### Task 3: Add DeepSeek classification and fallback behavior

**Files:**
- Modify: `D:/minimind/.worktrees/minimind-job-agent/evals/sales_copilot/signal_reclassifier.py`
- Test: `D:/minimind/.worktrees/minimind-job-agent/tests/evals/test_signal_reclassifier.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_reclassify_signal_candidates_uses_llm_response():
    llm_client = StubLLMClient(
        response={
            "classified_signals": [
                {
                    "candidate_id": "sig_001",
                    "predicted_label": "timeline_signals",
                    "confidence": 0.72,
                    "alternative_labels": ["next_steps"],
                    "notes": "time first",
                }
            ]
        }
    )
    candidates = [{"candidate_id": "sig_001", "text": "订单完成后帮助修改", "speaker": "agent", "evidence": "订单完成后帮助修改"}]
    rows = reclassify_signal_candidates(candidates, llm_client=llm_client, conversation_context="客服说明订单完成后帮助修改")
    assert rows[0]["predicted_label"] == "timeline_signals"
    assert rows[0]["text"] == "订单完成后帮助修改"


def test_apply_signal_fallback_moves_obvious_time_phrase_when_confidence_low():
    classified = [
        {
            "candidate_id": "sig_001",
            "text": "订单完成后帮助修改",
            "predicted_label": "next_steps",
            "confidence": 0.31,
            "alternative_labels": ["timeline_signals"],
            "notes": "",
        }
    ]
    corrected = apply_signal_fallback(classified)
    assert "timeline_signals" in corrected[0]["final_labels"]
```

- [ ] **Step 2: Run test to verify it fails**

Run the same test file and expect FAIL because reclassification/fallback helpers are missing.

- [ ] **Step 3: Write minimal implementation**

```python
def reclassify_signal_candidates(candidates: list[dict[str, object]], *, llm_client, conversation_context: str) -> list[dict[str, object]]:
    if not candidates:
        return []
    messages = build_signal_reclassification_messages(
        conversation_context=conversation_context,
        signal_candidates=[
            {
                "candidate_id": row["candidate_id"],
                "text": row["text"],
                "speaker": row.get("speaker", "agent"),
                "evidence": row.get("evidence", row["text"]),
            }
            for row in candidates
        ],
    )
    payload = llm_client.complete(messages)
    classified = payload.get("classified_signals", [])
    by_id = {row["candidate_id"]: row for row in candidates}
    normalized = []
    for row in classified:
        candidate = by_id.get(row.get("candidate_id"))
        if not candidate:
            continue
        normalized.append(
            {
                "candidate_id": candidate["candidate_id"],
                "text": candidate["text"],
                "predicted_label": row.get("predicted_label", "other"),
                "confidence": float(row.get("confidence", 0.0)),
                "alternative_labels": row.get("alternative_labels", []),
                "notes": row.get("notes", ""),
            }
        )
    return normalized


def apply_signal_fallback(classified_signals: list[dict[str, object]]) -> list[dict[str, object]]:
    result = []
    for row in classified_signals:
        labels = [row["predicted_label"]] if row.get("predicted_label") else []
        text = str(row.get("text", ""))
        confidence = float(row.get("confidence", 0.0))
        if confidence < 0.5 and any(token in text for token in ("工作日内", "今天", "明天", "之后", "完成后")):
            if "timeline_signals" not in labels:
                labels.append("timeline_signals")
        if confidence < 0.5 and any(token in text for token in ("退款", "补偿", "优惠券", "差价", "返还")):
            if "budget_signals" not in labels:
                labels.append("budget_signals")
        if any(token in text for token in ("联系客服", "申请退款", "重新下单", "留下信息")):
            if "next_steps" not in labels:
                labels.append("next_steps")
        result.append({**row, "final_labels": labels})
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_signal_reclassifier.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add D:/minimind/.worktrees/minimind-job-agent/evals/sales_copilot/signal_reclassifier.py D:/minimind/.worktrees/minimind-job-agent/tests/evals/test_signal_reclassifier.py
git commit -m "feat: add DeepSeek signal reclassification pipeline"
```

### Task 4: Wire reclassification into CSDS runner behind a flag

**Files:**
- Modify: `D:/minimind/.worktrees/minimind-job-agent/evals/sales_copilot/csds_runner.py`
- Test: `D:/minimind/.worktrees/minimind-job-agent/tests/evals/test_csds_runner.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_build_case_result_uses_reclassification_when_enabled(monkeypatch):
    case = make_csds_case()
    monkeypatch.setattr(
        "evals.sales_copilot.csds_runner._run_parse_step",
        lambda case, llm_client: {
            "account_name": "京东客服",
            "customer_roles": ["用户", "客服"],
            "confirmed_needs": ["修改订单信息"],
            "budget_signals": [],
            "timeline_signals": [],
            "next_steps": ["订单完成后帮助修改"],
            "competitors": [],
            "objections": [],
        },
    )
    monkeypatch.setattr(
        "evals.sales_copilot.csds_runner.reclassify_parse_result",
        lambda parse_result, llm_client, source_note: {**parse_result, "timeline_signals": ["订单完成后"]},
    )
    row = _build_case_result(case, llm_client=object(), use_signal_reclassification=True)
    assert row["parse_result"]["timeline_signals"] == ["订单完成后"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_csds_runner.py -q
```

Expected: FAIL because the runner does not accept the new flag/path yet.

- [ ] **Step 3: Write minimal implementation**

```python
def _build_case_result(case: CSDSCase, *, llm_client, use_signal_reclassification: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    parse_result: dict[str, Any] = {}
    try:
        parse_result = _run_parse_step(case, llm_client=llm_client)
        if use_signal_reclassification:
            parse_result = reclassify_parse_result(
                parse_result,
                llm_client=llm_client,
                source_note=case["source_note"],
            )
    except Exception as exc:
        errors.append(f"parse error: {exc}")
```

Also thread `use_signal_reclassification` through:
- `run_csds_parse_evaluation(...)`
- `run_full_csds_parse_evaluation(...)`

- [ ] **Step 4: Run test to verify it passes**

Run the same pytest command and expect PASS.

- [ ] **Step 5: Commit**

```bash
git add D:/minimind/.worktrees/minimind-job-agent/evals/sales_copilot/csds_runner.py D:/minimind/.worktrees/minimind-job-agent/tests/evals/test_csds_runner.py
git commit -m "feat: add optional signal reclassification to csds eval"
```

### Task 5: Expose CLI flag and document usage

**Files:**
- Modify: `D:/minimind/.worktrees/minimind-job-agent/scripts/run_sales_copilot_eval.py`
- Modify: `D:/minimind/.worktrees/minimind-job-agent/README.md`
- Test: `D:/minimind/.worktrees/minimind-job-agent/tests/evals/test_csds_runner.py`

- [ ] **Step 1: Write the failing test**

```python
def test_full_csds_eval_cli_threads_signal_reclassification_flag(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "scripts.run_sales_copilot_eval.run_full_csds_parse_evaluation",
        lambda **kwargs: captured.update(kwargs) or {
            "summary": {"total_cases": 0, "parse": {}},
            "case_results": [],
        },
    )
    # invoke parser/main with --use-signal-reclassification
    assert captured["use_signal_reclassification"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run the CLI-focused test and expect FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
parser.add_argument(\"--use-signal-reclassification\", action=\"store_true\")
...
bundle = run_full_csds_parse_evaluation(
    ...,
    use_signal_reclassification=args.use_signal_reclassification,
)
```

Update README with:

```md
### CSDS parse-only reclassification mode

Use `--use-signal-reclassification` to enable a DeepSeek second-pass classifier for
`budget_signals`, `timeline_signals`, and `next_steps` during CSDS evaluation.
```

- [ ] **Step 4: Run test to verify it passes**

Run the targeted CLI test and expect PASS.

- [ ] **Step 5: Commit**

```bash
git add D:/minimind/.worktrees/minimind-job-agent/scripts/run_sales_copilot_eval.py D:/minimind/.worktrees/minimind-job-agent/README.md D:/minimind/.worktrees/minimind-job-agent/tests/evals/test_csds_runner.py
git commit -m "docs: expose signal reclassification eval mode"
```

### Task 6: Run A/B verification on CSDS test-800

**Files:**
- Use generated outputs under: `D:/minimind/.worktrees/minimind-job-agent/evals/sales_copilot/`

- [ ] **Step 1: Run baseline tests**

Run:

```powershell
& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest D:\minimind\.worktrees\minimind-job-agent\tests\evals D:\minimind\.worktrees\minimind-job-agent\tests\sales_copilot\test_prompts.py -q
```

Expected: PASS.

- [ ] **Step 2: Run baseline CSDS test-800**

Run:

```powershell
$env:DEEPSEEK_API_KEY='...'
& 'D:\anaconda\envs\minimind_job_agent\python.exe' D:\minimind\.worktrees\minimind-job-agent\scripts\run_sales_copilot_eval.py --dataset-kind full-csds --csds-data-dir D:\minimind\.worktrees\minimind-job-agent\tmp_csds_download --csds-splits test --output-dir D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_csds_full_reclass_baseline --mode offline
```

Expected: report bundle is written.

- [ ] **Step 3: Run reclassification CSDS test-800**

Run:

```powershell
$env:DEEPSEEK_API_KEY='...'
& 'D:\anaconda\envs\minimind_job_agent\python.exe' D:\minimind\.worktrees\minimind-job-agent\scripts\run_sales_copilot_eval.py --dataset-kind full-csds --csds-data-dir D:\minimind\.worktrees\minimind-job-agent\tmp_csds_download --csds-splits test --output-dir D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_csds_full_reclass_enabled --mode offline --use-signal-reclassification
```

Expected: report bundle is written.

- [ ] **Step 4: Compare metrics**

Check:
- `json_valid_rate`
- `average_list_field_f1`
- `budget_signals`
- `timeline_signals`
- `next_steps`

Expected: weak-field improvement without JSON validity regression.

- [ ] **Step 5: Commit**

```bash
git add D:/minimind/.worktrees/minimind-job-agent
git commit -m "feat: validate signal reclassification on csds eval"
```
