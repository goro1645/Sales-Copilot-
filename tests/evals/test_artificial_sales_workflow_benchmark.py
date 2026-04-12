from __future__ import annotations

from evals.sales_copilot.artificial_sales_workflow_benchmark import (
    ARTIFICIAL_PHASE_TARGETS,
    ARTIFICIAL_ROUTE_TARGETS,
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
        "funnel_phase": "commercial_progression",
        "target_route": "high_priority_follow_up",
        "customer_profile_text": "Merchant profile",
        "meeting_note_text": "Meeting note",
        "expected_parse": {
            "account_name": "Merchant A",
            "customer_roles": ["ae", "merchant_ops"],
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


def test_validate_authored_case_requires_expected_route_to_match_target_route() -> None:
    row = {
        "case_id": "artificial_sales_002",
        "segment": "artificial_sales_workflow_benchmark",
        "source_case_type": "merchant_onboarding",
        "funnel_phase": "initial_contact",
        "target_route": "high_priority_follow_up",
        "customer_profile_text": "Merchant profile",
        "meeting_note_text": "Merchant note",
        "expected_parse": {
            "account_name": "Merchant B",
            "customer_roles": ["ae", "founder"],
            "confirmed_needs": ["reporting dashboard"],
            "objections": [],
            "next_steps": ["send deck"],
            "budget_signals": ["budget approved"],
            "timeline_signals": ["this week"],
            "competitors": [],
        },
        "expected_workflow": {
            "lead_score_range": [60, 75],
            "lead_priority": "medium",
            "opportunity_stage": "qualification",
            "expected_route": "standard_follow_up",
            "expected_crm_writeback": {
                "should_write": True,
                "account_status": "qualified_opportunity",
                "opportunity_stage": "qualification",
                "risk_flags": ["stakeholder_incomplete"],
                "recommended_next_step": "send deck",
                "evidence": ["merchant asked for details"],
                "acceptable_variants": [],
            },
            "expected_task_bundle": {
                "should_generate": True,
                "tasks": [],
                "acceptable_variants": [],
            },
        },
        "author_note": "Mismatch test",
    }

    try:
        validate_authored_case(row)
    except ValueError as exc:
        assert "expected_route" in str(exc)
    else:
        raise AssertionError("validate_authored_case should reject route mismatches")


def test_write_artificial_sales_readme_includes_route_distribution(tmp_path) -> None:
    rows = [
        {
            "funnel_phase": "initial_contact",
            "expected_workflow": {"expected_route": "high_priority_follow_up"},
        },
        {
            "funnel_phase": "nurture_deferred",
            "expected_workflow": {"expected_route": "low_priority_nurture"},
        },
    ]
    path = tmp_path / "README.md"
    write_artificial_sales_readme(path, rows)

    content = path.read_text(encoding="utf-8")
    assert "Artificial Sales Workflow Benchmark 50" in content
    assert "`high_priority_follow_up`: 1" in content
    assert "`low_priority_nurture`: 1" in content
