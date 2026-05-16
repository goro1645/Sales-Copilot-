from __future__ import annotations

from pathlib import Path

from scripts import build_workflow_calibrated_benchmark


def test_build_workflow_calibrated_benchmark_cli_writes_final_files(monkeypatch, tmp_path: Path) -> None:
    source_path = tmp_path / "source.jsonl"
    source_path.write_text(
        (
            '{"case_id":"case_1","source_dataset":"full-csds-ai-calibrated","meeting_note_text":"Budget confirmed and proposal needed next week.",'
            '"customer_profile_text":"Source: CSDS","expected_parse":{"account_name":"A","customer_roles":[],"confirmed_needs":["proposal"],'
            '"budget_signals":["budget confirmed"],"timeline_signals":["next week"],"next_steps":["send proposal"],"competitors":[]}}\n'
        ),
        encoding="utf-8",
    )

    class _FakeClient:
        def complete_with_tool(self, messages, tools, tool_choice):
            return {
                "tool_name": "submit_ai_calibrated_workflow",
                "arguments": {
                    "expected_workflow": {
                        "lead_score_range": [80, 90],
                        "lead_priority": "high",
                        "opportunity_stage": "proposal",
                        "expected_route": "high_priority_follow_up",
                        "expected_crm_writeback": {
                            "should_write": True,
                            "account_status": "active",
                            "opportunity_stage": "proposal",
                            "risk_flags": ["approved_budget"],
                            "recommended_next_step": "send proposal",
                            "evidence": ["budget confirmed"],
                            "acceptable_variants": [],
                        },
                        "expected_task_bundle": {
                            "should_generate": True,
                            "tasks": [
                                {
                                    "title": "send proposal",
                                    "description": "Send proposal",
                                    "priority": "high",
                                    "owner": "Sales",
                                    "timing_expectation": "next_day",
                                    "evidence": ["proposal requested"],
                                }
                            ],
                            "acceptable_variants": [],
                        },
                    },
                    "calibration_note": "AI draft",
                },
            }

    monkeypatch.setattr(build_workflow_calibrated_benchmark, "_build_deepseek_client", lambda api_key, base_url, model: _FakeClient())
    monkeypatch.setattr(
        "sys.argv",
        [
            "build_workflow_calibrated_benchmark.py",
            "--source-jsonl",
            str(source_path),
            "--api-key",
            "test-key",
            "--output-dir",
            str(tmp_path / "outputs"),
        ],
    )

    assert build_workflow_calibrated_benchmark.main() == 0
    assert (tmp_path / "outputs" / "full_csds_workflow_calibrated_30.jsonl").exists()
    assert (tmp_path / "outputs" / "full_csds_workflow_calibrated_30_README.md").exists()
