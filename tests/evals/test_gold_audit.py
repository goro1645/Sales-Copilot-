from __future__ import annotations

from evals.sales_copilot.gold_audit import (
    assign_audit_bucket,
    build_audit_row,
    build_stratified_audit_sample,
    summarize_gold_audit_rows,
)


def _build_case(
    case_id: str,
    *,
    budget_signals: list[str] | None = None,
    timeline_signals: list[str] | None = None,
    next_steps: list[str] | None = None,
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "source_uid": case_id.removeprefix("case_"),
        "source_split": "test",
        "meeting_note_text": "客服表示会在明天回电，并且商品价格已经很优惠。",
        "expected_parse": {
            "account_name": "京东客服",
            "customer_roles": ["用户", "客服"],
            "confirmed_needs": ["用户询问订单进展"],
            "budget_signals": budget_signals or [],
            "timeline_signals": timeline_signals or [],
            "next_steps": next_steps or [],
            "competitors": [],
        },
    }


def test_assign_audit_bucket_prioritizes_overlap_cases() -> None:
    case = _build_case(
        "case_overlap",
        timeline_signals=["客服表示会在明天回电。"],
        next_steps=["客服表示会在明天回电。"],
    )

    assert assign_audit_bucket(case) == "field_overlap_high_risk"


def test_build_stratified_audit_sample_preserves_requested_bucket_sizes() -> None:
    cases = [
        _build_case("case_ordinary_1", next_steps=["客服回复处理中。"]),
        _build_case("case_ordinary_2", next_steps=["客服回复处理中。"]),
        _build_case("case_timeline_1", timeline_signals=["明天回复"], next_steps=["客服处理中。"]),
        _build_case("case_timeline_2", timeline_signals=["一个工作日内到账"], next_steps=["客服处理中。"]),
        _build_case("case_budget_1", budget_signals=["支持退款"], next_steps=["客服处理中。"]),
        _build_case("case_budget_2", budget_signals=["优惠券无法补发"], next_steps=["客服处理中。"]),
        _build_case(
            "case_overlap_1",
            timeline_signals=["客服表示会在明天回电。"],
            next_steps=["客服表示会在明天回电。"],
        ),
        _build_case(
            "case_overlap_2",
            budget_signals=["客服表示价格已经很优惠了。"],
            next_steps=["客服表示价格已经很优惠了。"],
        ),
    ]

    rows = build_stratified_audit_sample(
        cases,
        bucket_targets={
            "ordinary": 2,
            "timeline_nonempty": 2,
            "budget_nonempty": 2,
            "field_overlap_high_risk": 2,
        },
    )

    bucket_counts: dict[str, int] = {}
    for row in rows:
        bucket = str(row["audit_bucket"])
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1

    assert bucket_counts == {
        "ordinary": 2,
        "timeline_nonempty": 2,
        "budget_nonempty": 2,
        "field_overlap_high_risk": 2,
    }


def test_build_audit_row_marks_overlap_flags() -> None:
    case = _build_case(
        "case_overlap",
        timeline_signals=["客服表示会在明天回电。"],
        budget_signals=["客服表示价格已经很优惠了。"],
        next_steps=["客服表示会在明天回电。", "客服表示价格已经很优惠了。"],
    )
    raw_row = {
        "UserSumm": ["用户询问什么时候回复。"],
        "AgentSumm": ["客服表示会在明天回电。", "客服表示价格已经很优惠了。"],
        "FinalSumm": ["客服表示会在明天回电。", "客服表示价格已经很优惠了。"],
    }

    row = build_audit_row(case, raw_row=raw_row, audit_bucket="field_overlap_high_risk")

    assert row["heuristic_flags"]["timeline_next_overlap"] is True
    assert row["heuristic_flags"]["budget_next_overlap"] is True
    assert row["audit_label"] == ""
    assert row["audit_note"] == ""


def test_summarize_gold_audit_rows_counts_overlap_and_warning_flags() -> None:
    rows = [
        {
            "audit_bucket": "ordinary",
            "heuristic_flags": {
                "timeline_next_overlap": False,
                "budget_next_overlap": False,
                "timeline_contains_non_time_like_sentence": False,
            },
        },
        {
            "audit_bucket": "field_overlap_high_risk",
            "heuristic_flags": {
                "timeline_next_overlap": True,
                "budget_next_overlap": False,
                "timeline_contains_non_time_like_sentence": True,
            },
        },
    ]

    summary = summarize_gold_audit_rows(rows)

    assert summary["total_rows"] == 2
    assert summary["bucket_counts"]["ordinary"] == 1
    assert summary["bucket_counts"]["field_overlap_high_risk"] == 1
    assert summary["heuristic_flag_counts"]["timeline_next_overlap"] == 1
    assert summary["heuristic_flag_counts"]["timeline_contains_non_time_like_sentence"] == 1
