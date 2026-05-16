# Sales Copilot Tool-Call Signal Reclassification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace freeform JSON second-pass signal reclassification with DeepSeek tool-call based constrained classification, then verify the output path on a `20`-case `CSDS` smoke run.

**Architecture:** Keep the first-pass parse unchanged, extract weak-field candidates, force DeepSeek to call a single classification function, and merge the results additively into the parse output. The client layer gains a non-streaming tool-call helper; the eval path gains batch-level classification and explicit reclassification error reporting.

**Tech Stack:** Python, DeepSeek Chat Completions, function/tool calls, pytest

---

### Task 1: Add failing tests for non-streaming DeepSeek tool-call parsing

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\tests\llm\test_deepseek_client.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\llm\deepseek_client.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_complete_with_tool_returns_tool_arguments_json():
    client = DeepSeekClient(api_key="test-key")
    response_payload = {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "classify_signal_candidates",
                                "arguments": '{"classifications":[{"candidate_id":"sig_001","label":"timeline_signals"}]}',
                            },
                        }
                    ]
                }
            }
        ]
    }
    with patch("llm.deepseek_client.requests.post") as mocked_post:
        mocked_post.return_value.json.return_value = response_payload
        mocked_post.return_value.raise_for_status.return_value = None

        result = client.complete_with_tool(
            messages=[{"role": "user", "content": "classify"}],
            tools=[{"type": "function", "function": {"name": "classify_signal_candidates"}}],
            tool_choice={"type": "function", "function": {"name": "classify_signal_candidates"}},
        )

    assert result["tool_name"] == "classify_signal_candidates"
    assert result["arguments"]["classifications"][0]["label"] == "timeline_signals"


def test_complete_with_tool_raises_when_tool_call_missing():
    client = DeepSeekClient(api_key="test-key")
    response_payload = {"choices": [{"message": {"content": "plain text"}}]}
    with patch("llm.deepseek_client.requests.post") as mocked_post:
        mocked_post.return_value.json.return_value = response_payload
        mocked_post.return_value.raise_for_status.return_value = None

        with pytest.raises(ValueError, match="tool_calls"):
            client.complete_with_tool(
                messages=[{"role": "user", "content": "classify"}],
                tools=[{"type": "function", "function": {"name": "classify_signal_candidates"}}],
                tool_choice={"type": "function", "function": {"name": "classify_signal_candidates"}},
            )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest `
  'D:\minimind\.worktrees\minimind-job-agent\tests\llm\test_deepseek_client.py' -q
```

Expected: FAIL because `DeepSeekClient.complete_with_tool` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Implement a new helper on `DeepSeekClient`:

```python
def complete_with_tool(self, messages: list[dict], tools: list[dict], tool_choice: dict) -> dict[str, Any]:
    payload = {
        "model": self.model,
        "messages": list(messages),
        "temperature": 0.0,
        "stream": False,
        "tools": list(tools),
        "tool_choice": tool_choice,
    }
    response = requests.post(f"{self.base_url}/chat/completions", headers=self._headers(), json=payload, timeout=120)
    response.raise_for_status()
    data = response.json()
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("DeepSeek response has empty or invalid choices")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise ValueError("DeepSeek response choice is missing message")
    tool_calls = message.get("tool_calls")
    if not isinstance(tool_calls, list) or not tool_calls:
        raise ValueError("DeepSeek response is missing tool_calls")
    first_call = tool_calls[0]
    function = first_call.get("function") or {}
    tool_name = function.get("name")
    if not isinstance(tool_name, str) or not tool_name:
        raise ValueError("DeepSeek tool_call is missing function name")
    arguments_text = function.get("arguments")
    if not isinstance(arguments_text, str) or not arguments_text.strip():
        raise ValueError("DeepSeek tool_call is missing arguments")
    arguments = json.loads(arguments_text)
    if not isinstance(arguments, dict):
        raise ValueError("DeepSeek tool_call arguments must decode to a JSON object")
    return {"tool_name": tool_name, "arguments": arguments, "raw_response": data}
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest `
  'D:\minimind\.worktrees\minimind-job-agent\tests\llm\test_deepseek_client.py' -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/llm/test_deepseek_client.py llm/deepseek_client.py
git commit -m "feat: add DeepSeek non-streaming tool call helper"
```

### Task 2: Add failing tests for tool-call based signal reclassification

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_signal_reclassifier.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\sales_copilot\prompts.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\signal_reclassifier.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_reclassify_signal_candidates_uses_tool_call_schema():
    client = Mock()
    client.complete_with_tool.return_value = {
        "tool_name": "classify_signal_candidates",
        "arguments": {
            "classifications": [
                {"candidate_id": "sig_001", "label": "timeline_signals"}
            ]
        },
    }
    result = reclassify_signal_candidates(
        [{"candidate_id": "sig_001", "text": "订单完成后", "speaker": "agent", "evidence": "订单完成后"}],
        llm_client=client,
        conversation_context="customer-service note",
    )
    assert result[0]["predicted_label"] == "timeline_signals"
    assert client.complete_with_tool.called


def test_project_reclassified_parse_result_adds_without_clearing_existing_next_steps():
    parse_result = {
        "budget_signals": [],
        "timeline_signals": [],
        "next_steps": ["联系客服提供信息"],
    }
    classified = [
        {"text": "订单完成后", "final_labels": ["timeline_signals"]},
    ]
    projected = project_reclassified_parse_result(parse_result, classified)
    assert projected["next_steps"] == ["联系客服提供信息"]
    assert projected["timeline_signals"] == ["订单完成后"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest `
  'D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_signal_reclassifier.py' -q
```

Expected: FAIL because the reclassifier still expects freeform JSON and currently clears target fields during projection.

- [ ] **Step 3: Write minimal implementation**

Update the prompt helper to expose a tool-call friendly instruction:

```python
def build_signal_reclassification_messages(*, conversation_context: str, signal_candidates: list[dict]) -> list[dict[str, str]]:
    system_prompt = (
        "You are a customer-service signal classifier. "
        "You must classify each candidate by calling the classify_signal_candidates function. "
        "Do not answer with plain text."
    )
```

Update `signal_reclassifier.py` to:

- define a `_classification_tool_schema()` helper
- call `llm_client.complete_with_tool(...)`
- validate `classifications`
- map each item into:

```python
{
    "candidate_id": candidate["candidate_id"],
    "text": candidate["text"],
    "predicted_label": label,
}
```

Change projection to additive merge:

```python
projected = dict(parse_result)
for field in TARGET_FIELDS:
    existing = projected.get(field, [])
    projected[field] = list(existing) if isinstance(existing, list) else []
```

Only append new values, never clear existing ones.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest `
  'D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_signal_reclassifier.py' -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/evals/test_signal_reclassifier.py sales_copilot/prompts.py evals/sales_copilot/signal_reclassifier.py
git commit -m "feat: switch signal reclassifier to DeepSeek tool calls"
```

### Task 3: Add runner coverage for separated parse and reclassification errors

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_csds_runner.py`
- Modify: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\csds_runner.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_run_csds_parse_evaluation_records_reclassification_error_without_parse_error(tmp_path: Path) -> None:
    cases_path = tmp_path / "csds_cases.jsonl"
    cases_path.write_text(json.dumps(_build_case("csds-1"), ensure_ascii=False) + "\\n", encoding="utf-8")
    llm = ParseOnlyLLM()

    with patch(
        "evals.sales_copilot.csds_runner.reclassify_parse_result",
        side_effect=ValueError("tool classification batch failed"),
    ):
        bundle = run_csds_parse_evaluation(
            cases_path=cases_path,
            output_dir=tmp_path / "outputs",
            llm_client=llm,
            use_signal_reclassification=True,
        )

    row = bundle["case_results"][0]
    assert row["errors"] == []
    assert row["parse_errors"] == []
    assert row["reclassification_errors"] == ["signal reclassification error: tool classification batch failed"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest `
  'D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_csds_runner.py' -q
```

Expected: FAIL if the runner still reports reclassification issues as top-level parse errors.

- [ ] **Step 3: Write minimal implementation**

Keep the split already started in `csds_runner.py`:

- parse failures populate `parse_errors`
- reclassification failures populate `reclassification_errors`
- `errors` and `error` remain parse-only summaries

If needed, normalize the reclassification error message to one format:

```python
reclassification_errors.append(f"signal reclassification error: {exc}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest `
  'D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_csds_runner.py' -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/evals/test_csds_runner.py evals/sales_copilot/csds_runner.py
git commit -m "fix: separate parse and reclassification error reporting"
```

### Task 4: Run targeted regression and inspect a 20-case smoke output

**Files:**
- Modify: `D:\minimind\.worktrees\minimind-job-agent\README.md`
- Inspect output under: `D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_csds_toolcall_smoke`

- [ ] **Step 1: Run focused regression tests**

Run:

```powershell
& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest `
  'D:\minimind\.worktrees\minimind-job-agent\tests\llm\test_deepseek_client.py' `
  'D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_signal_reclassifier.py' `
  'D:\minimind\.worktrees\minimind-job-agent\tests\evals\test_csds_runner.py' -q
```

Expected: PASS

- [ ] **Step 2: Run the 20-case smoke evaluation**

Run:

```powershell
$env:DEEPSEEK_API_KEY="your_key"
$env:HF_HOME='D:\hf_cache\huggingface'
$env:SENTENCE_TRANSFORMERS_HOME='D:\hf_cache\sentence_transformers'
& 'D:\anaconda\envs\minimind_job_agent\python.exe' `
  'D:\minimind\.worktrees\minimind-job-agent\scripts\run_sales_copilot_eval.py' `
  --dataset-kind full-csds `
  --csds-data-dir 'D:\minimind\.worktrees\minimind-job-agent\tmp_csds_download' `
  --csds-splits test `
  --limit 20 `
  --output-dir 'D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_csds_toolcall_smoke' `
  --mode offline `
  --use-signal-reclassification
```

Expected: successful report bundle created under a timestamped subdirectory.

- [ ] **Step 3: Inspect smoke output format**

Inspect:

```powershell
Get-ChildItem 'D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_csds_toolcall_smoke' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
```

Then inspect the first few results:

```powershell
@'
import json
from pathlib import Path
root = Path(r'D:\minimind\.worktrees\minimind-job-agent\evals\sales_copilot\outputs_csds_toolcall_smoke')
latest = sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)[0]
rows = [json.loads(line) for line in (latest / 'case_results.jsonl').open('r', encoding='utf-8')]
for row in rows[:5]:
    print({
        'case_id': row['case_id'],
        'parse_errors': row.get('parse_errors'),
        'reclassification_errors': row.get('reclassification_errors'),
        'next_steps': row.get('parse_result', {}).get('next_steps'),
        'timeline_signals': row.get('parse_result', {}).get('timeline_signals'),
        'budget_signals': row.get('parse_result', {}).get('budget_signals'),
    })
'@ | & 'D:\anaconda\envs\minimind_job_agent\python.exe' -
```

Expected:
- tool-call batches return stable structured classifications
- `parse_errors` stays empty
- `next_steps` is preserved even when reclassification fails

- [ ] **Step 4: Document the new tool-call reclassification path**

Add a short README note covering:

- the feature uses DeepSeek tool calls rather than freeform JSON
- the current recommended validation path is a `20`-case smoke run before any full `800`-case rerun

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: document tool-call reclassification smoke validation"
```
