from __future__ import annotations

from pathlib import Path

from scripts import build_artificial_sales_workflow_benchmark


def test_build_artificial_sales_workflow_benchmark_cli_writes_outputs(
    monkeypatch, tmp_path: Path
) -> None:
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

    monkeypatch.setattr(
        build_artificial_sales_workflow_benchmark,
        "_build_deepseek_client",
        lambda api_key, base_url, model: _FakeClient(),
    )
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

