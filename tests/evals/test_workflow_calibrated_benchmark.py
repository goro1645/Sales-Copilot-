from __future__ import annotations

from evals.sales_copilot.workflow_calibrated_benchmark import (
    build_workflow_calibrated_sample,
    export_final_workflow_calibrated_rows,
    infer_workflow_sampling_bucket,
)


def _build_row(
    case_id: str,
    *,
    expected_parse: dict[str, object],
    meeting_note_text: str = "baseline note",
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "source_dataset": "full-csds-ai-calibrated",
        "meeting_note_text": meeting_note_text,
        "customer_profile_text": "Source: CSDS",
        "expected_parse": expected_parse,
    }


def test_infer_workflow_sampling_bucket_identifies_need_more_info() -> None:
    row = _build_row(
        "case_need_info",
        expected_parse={
            "account_name": "JD Support",
            "customer_roles": ["user", "agent"],
            "confirmed_needs": ["integration support"],
            "budget_signals": [],
            "timeline_signals": [],
            "next_steps": [],
            "competitors": [],
        },
        meeting_note_text="Customer is interested but budget and timeline are still unclear.",
    )

    assert infer_workflow_sampling_bucket(row) == "need_more_info"


def test_build_workflow_calibrated_sample_hits_route_targets() -> None:
    rows = []
    for index in range(10):
        rows.append(
            _build_row(
                f"high_{index}",
                expected_parse={
                    "account_name": "A",
                    "customer_roles": [],
                    "confirmed_needs": ["proposal"],
                    "budget_signals": ["budget confirmed"],
                    "timeline_signals": ["next week"],
                    "next_steps": ["send proposal"],
                    "competitors": [],
                },
                meeting_note_text="Budget confirmed and proposal needed next week.",
            )
        )
    for index in range(10):
        rows.append(
            _build_row(
                f"standard_{index}",
                expected_parse={
                    "account_name": "B",
                    "customer_roles": [],
                    "confirmed_needs": ["solution details"],
                    "budget_signals": [],
                    "timeline_signals": [],
                    "next_steps": ["follow up with details"],
                    "competitors": [],
                },
                meeting_note_text="Needs follow-up with solution details.",
            )
        )
    for index in range(10):
        rows.append(
            _build_row(
                f"nurture_{index}",
                expected_parse={
                    "account_name": "C",
                    "customer_roles": [],
                    "confirmed_needs": ["reference material"],
                    "budget_signals": [],
                    "timeline_signals": [],
                    "next_steps": ["send reference material"],
                    "competitors": [],
                },
                meeting_note_text="Send reference material and revisit next year.",
            )
        )
    for index in range(10):
        rows.append(
            _build_row(
                f"need_{index}",
                expected_parse={
                    "account_name": "D",
                    "customer_roles": [],
                    "confirmed_needs": ["crm integration"],
                    "budget_signals": [],
                    "timeline_signals": [],
                    "next_steps": [],
                    "competitors": [],
                },
                meeting_note_text="Interested but budget and timeline are not confirmed yet.",
            )
        )

    sample = build_workflow_calibrated_sample(rows)

    bucket_counts: dict[str, int] = {}
    for row in sample:
        bucket = str(row["workflow_sampling_bucket"])
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1

    assert len(sample) == 30
    assert bucket_counts["high_priority_follow_up"] == 8
    assert bucket_counts["standard_follow_up"] == 8
    assert bucket_counts["low_priority_nurture"] == 7
    assert bucket_counts["need_more_info"] == 7


def test_export_final_workflow_calibrated_rows_builds_compatibility_fields() -> None:
    rows = [
        {
            "case_id": "case_1",
            "segment": "workflow_calibrated_subset",
            "source_dataset": "full-csds-ai-calibrated",
            "meeting_note_text": "m",
            "customer_profile_text": "c",
            "expected_parse": {
                "account_name": "JD Support",
                "customer_roles": ["user", "agent"],
                "confirmed_needs": ["proposal"],
                "budget_signals": ["budget confirmed"],
                "timeline_signals": ["next week"],
                "next_steps": ["send proposal"],
                "competitors": [],
            },
            "workflow_review": {
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
                        "acceptable_variants": ["share proposal"],
                    },
                    "expected_task_bundle": {
                        "should_generate": True,
                        "tasks": [
                            {
                                "title": "send proposal",
                                "description": "Send a formal proposal.",
                                "priority": "high",
                                "owner": "Sales",
                                "timing_expectation": "next_day",
                                "evidence": ["proposal requested"],
                            }
                        ],
                        "acceptable_variants": ["share proposal deck"],
                    },
                },
                "calibration_note": "AI draft",
            },
        }
    ]

    final_rows = export_final_workflow_calibrated_rows(rows)
    workflow = final_rows[0]["expected_workflow"]

    assert workflow["should_write_crm"] is True
    assert workflow["should_generate_tasks"] is True
    assert workflow["required_task_titles"] == ["send proposal"]
    assert workflow["required_risk_flags"] == ["approved_budget"]
