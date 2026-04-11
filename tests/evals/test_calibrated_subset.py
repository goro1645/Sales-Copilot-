from __future__ import annotations

from evals.sales_copilot.calibrated_subset import (
    build_calibrated_sample,
    build_calibrated_working_rows,
    export_final_calibrated_rows,
)


def _build_case(
    case_id: str,
    *,
    meeting_note_text: str = "Customer asks about order handling. Agent says they will reply tomorrow and coupon cannot be reused.",
    user_summ: list[str] | None = None,
    agent_summ: list[str] | None = None,
    final_summ: list[str] | None = None,
    expected_parse: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "source_uid": case_id.removeprefix("case_"),
        "source_split": "test",
        "source_note": "full-csds sample",
        "meeting_note_text": meeting_note_text,
        "customer_profile_text": "Source: CSDS",
        "expected_parse": expected_parse
        or {
            "account_name": "JD Support",
            "customer_roles": ["user", "agent"],
            "confirmed_needs": ["check order handling progress"],
            "budget_signals": [],
            "timeline_signals": [],
            "next_steps": ["agent will follow up"],
            "competitors": [],
        },
        "_raw_row": {
            "UserSumm": user_summ or ["check order handling progress"],
            "AgentSumm": agent_summ or ["reply tomorrow and coupon cannot be reused"],
            "FinalSumm": final_summ or ["reply tomorrow and coupon cannot be reused"],
        },
    }


def test_build_calibrated_sample_hits_requested_bucket_sizes_with_backfill() -> None:
    cases: list[dict[str, object]] = []
    for index in range(40):
        cases.append(_build_case(f"case_ord_{index}"))
    for index in range(25):
        cases.append(
            _build_case(
                f"case_time_{index}",
                meeting_note_text="Agent says they will contact the customer tomorrow and finish within one business day.",
                agent_summ=["contact customer tomorrow and finish within one business day"],
                final_summ=["contact customer tomorrow and finish within one business day"],
            )
        )
    for index in range(10):
        cases.append(
            _build_case(
                f"case_budget_{index}",
                meeting_note_text="Agent says coupon cannot be reused and refund is available.",
                agent_summ=["coupon cannot be reused and refund is available"],
                final_summ=["coupon cannot be reused and refund is available"],
            )
        )
    for index in range(25):
        cases.append(
            _build_case(
                f"case_overlap_{index}",
                expected_parse={
                    "account_name": "JD Support",
                    "customer_roles": ["user", "agent"],
                    "confirmed_needs": ["handle order issue"],
                    "budget_signals": ["coupon cannot be reused"],
                    "timeline_signals": ["reply tomorrow"],
                    "next_steps": ["reply tomorrow", "coupon cannot be reused"],
                    "competitors": [],
                },
                agent_summ=["reply tomorrow and coupon cannot be reused"],
                final_summ=["reply tomorrow and coupon cannot be reused"],
            )
        )

    baseline_case_results = {
        "case_ord_0": {"parse_result": {"next_steps": ["agent will reply soon"]}},
        "case_overlap_0": {"parse_result": {"budget_signals": ["refund is available"], "next_steps": ["request refund"]}},
    }

    rows = build_calibrated_sample(
        cases,
        baseline_case_results=baseline_case_results,
        target_counts={
            "ordinary_stable": 25,
            "timeline_boundary": 20,
            "budget_boundary": 20,
            "field_overlap_high_risk": 20,
            "model_rule_conflict": 15,
        },
    )

    bucket_counts: dict[str, int] = {}
    for row in rows:
        bucket = str(row["sampling_bucket"])
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1

    assert len(rows) == 100
    assert bucket_counts["ordinary_stable"] == 25
    assert bucket_counts["timeline_boundary"] == 20
    assert bucket_counts["budget_boundary"] == 20
    assert bucket_counts["field_overlap_high_risk"] == 20
    assert bucket_counts["model_rule_conflict"] == 15


def test_build_calibrated_working_rows_seeds_pre_annotation_from_baseline() -> None:
    case = _build_case(
        "case_conflict",
        expected_parse={
            "account_name": "JD Support",
            "customer_roles": ["user", "agent"],
            "confirmed_needs": ["modify shipping address"],
            "budget_signals": [],
            "timeline_signals": [],
            "next_steps": ["agent will follow up"],
            "competitors": [],
        },
    )

    rows = build_calibrated_working_rows(
        [case],
        baseline_case_results={
            "case_conflict": {
                "parse_result": {
                    "account_name": "JD Support",
                    "customer_roles": ["user", "agent"],
                    "confirmed_needs": ["modify shipping address"],
                    "budget_signals": ["coupon cannot be reused"],
                    "timeline_signals": ["reply tomorrow"],
                    "next_steps": ["submit shipping change request"],
                    "competitors": [],
                }
            }
        },
    )

    row = rows[0]
    assert row["baseline_parse_result"]["budget_signals"] == ["coupon cannot be reused"]
    assert row["pre_annotation"]["budget_signals_decision"] == "edit"
    assert row["pre_annotation"]["needs_human_review"] is True
    assert row["human_review"] == {}


def test_export_final_calibrated_rows_prefers_human_review_when_present() -> None:
    rows = [
        {
            "case_id": "case_1",
            "meeting_note_text": "Agent says they will contact the customer tomorrow.",
            "expected_parse": {
                "account_name": "JD Support",
                "customer_roles": ["user", "agent"],
                "confirmed_needs": ["handle order issue"],
                "budget_signals": [],
                "timeline_signals": [],
                "next_steps": ["agent will follow up"],
                "competitors": [],
            },
            "pre_annotation": {
                "corrected_expected_parse": {
                    "confirmed_needs": ["handle order issue"],
                    "budget_signals": [],
                    "timeline_signals": ["contact tomorrow"],
                    "next_steps": ["contact customer"],
                }
            },
            "human_review": {
                "final_expected_parse": {
                    "confirmed_needs": ["handle order issue"],
                    "budget_signals": [],
                    "timeline_signals": ["contact tomorrow"],
                    "next_steps": ["contact support to proceed"],
                }
            },
        }
    ]

    final_rows = export_final_calibrated_rows(rows)

    assert final_rows[0]["expected_parse"]["next_steps"] == ["contact support to proceed"]
