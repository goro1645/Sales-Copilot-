import json
from pathlib import Path

import pytest

from evals.sales_copilot.cases import load_golden_cases


def _build_sales_case(
    case_id: str,
    *,
    segment: str,
    lead_score_range: list[int],
    lead_priority: str,
    opportunity_stage: str,
    expected_route: str,
    should_write_crm: bool,
    should_generate_tasks: bool,
    required_task_titles: list[str],
    required_risk_flags: list[str],
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "segment": segment,
        "customer_profile_text": "华东制造集团正在推进全国门店数字化采购升级，预算已在年度计划中预留。",
        "meeting_note_text": "客户明确表示本周要确认报价，并在下周启动三家门店试点，已经有内部审批人。",
        "expected_parse": {
            "account_name": "华东制造集团",
            "customer_roles": ["采购负责人", "业务总监"],
            "confirmed_needs": ["试点方案", "报价单", "交付排期"],
            "budget_signals": ["年度预算已预留", "可以先走采购流程"],
            "timeline_signals": ["本周确认报价", "下周启动试点"],
            "next_steps": ["发送正式报价单", "安排试点评审会"],
            "competitors": ["竞品A"],
        },
        "expected_workflow": {
            "lead_score_range": lead_score_range,
            "lead_priority": lead_priority,
            "opportunity_stage": opportunity_stage,
            "expected_route": expected_route,
            "should_write_crm": should_write_crm,
            "should_generate_tasks": should_generate_tasks,
            "required_task_titles": required_task_titles,
            "required_risk_flags": required_risk_flags,
        },
    }


def test_load_golden_cases_reads_repository_cases_with_formal_workflow_contract():
    path = Path(__file__).resolve().parents[2] / "evals" / "sales_copilot" / "golden_cases.jsonl"

    cases = load_golden_cases(path)
    by_case_id = {case["case_id"]: case for case in cases}

    assert list(by_case_id) == [
        "high_intent_complete",
        "high_intent_missing_facts",
        "medium_intent_nurture",
        "low_intent_or_noise",
    ]
    assert by_case_id["high_intent_complete"]["segment"] == "high_intent_complete"
    assert by_case_id["high_intent_complete"]["expected_workflow"]["opportunity_stage"] == "proposal"
    assert by_case_id["high_intent_complete"]["expected_workflow"]["lead_score_range"] == [90, 100]
    assert by_case_id["high_intent_complete"]["expected_workflow"]["should_write_crm"] is True
    assert by_case_id["high_intent_complete"]["expected_workflow"]["required_risk_flags"] == []

    assert by_case_id["high_intent_missing_facts"]["segment"] == "high_intent_missing_facts"
    assert by_case_id["high_intent_missing_facts"]["expected_workflow"]["opportunity_stage"] == "qualification"
    assert by_case_id["high_intent_missing_facts"]["expected_workflow"]["lead_score_range"] == [70, 79]
    assert by_case_id["high_intent_missing_facts"]["expected_workflow"]["should_write_crm"] is True
    assert by_case_id["high_intent_missing_facts"]["expected_workflow"]["required_risk_flags"] == [
        "missing_required_facts"
    ]

    assert by_case_id["medium_intent_nurture"]["segment"] == "medium_intent_nurture"
    assert by_case_id["medium_intent_nurture"]["expected_workflow"]["opportunity_stage"] == "discovery"
    assert by_case_id["medium_intent_nurture"]["expected_workflow"]["lead_score_range"] == [55, 69]
    assert by_case_id["medium_intent_nurture"]["expected_workflow"]["should_write_crm"] is True
    assert by_case_id["medium_intent_nurture"]["expected_workflow"]["required_risk_flags"] == []

    assert by_case_id["low_intent_or_noise"]["segment"] == "low_intent_or_noise"
    assert by_case_id["low_intent_or_noise"]["expected_workflow"]["opportunity_stage"] == "discovery"
    assert by_case_id["low_intent_or_noise"]["expected_workflow"]["lead_score_range"] == [0, 24]
    assert by_case_id["low_intent_or_noise"]["expected_workflow"]["should_write_crm"] is True
    assert by_case_id["low_intent_or_noise"]["expected_workflow"]["required_risk_flags"] == []


def test_load_golden_cases_raises_when_opportunity_stage_is_invalid(tmp_path):
    path = tmp_path / "invalid_stage.jsonl"
    path.write_text(
        json.dumps(
            _build_sales_case(
                "bad_stage",
                segment="medium_intent_nurture",
                lead_score_range=[55, 69],
                lead_priority="medium",
                opportunity_stage="pipeline",
                expected_route="standard_follow_up",
                should_write_crm=True,
                should_generate_tasks=True,
                required_task_titles=["发送案例资料"],
                required_risk_flags=[],
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="opportunity_stage"):
        load_golden_cases(path)


def test_load_golden_cases_raises_when_missing_required_facts_requires_tasks(tmp_path):
    path = tmp_path / "invalid_missing_facts.jsonl"
    path.write_text(
        json.dumps(
            _build_sales_case(
                "bad_missing_facts",
                segment="high_intent_missing_facts",
                lead_score_range=[70, 79],
                lead_priority="medium",
                opportunity_stage="qualification",
                expected_route="standard_follow_up",
                should_write_crm=True,
                should_generate_tasks=False,
                required_task_titles=[],
                required_risk_flags=["missing_required_facts"],
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing_required_facts"):
        load_golden_cases(path)


def test_load_golden_cases_raises_when_tasks_enabled_but_titles_missing(tmp_path):
    path = tmp_path / "missing_titles.jsonl"
    path.write_text(
        json.dumps(
            _build_sales_case(
                "missing_titles_case",
                segment="medium_intent_nurture",
                lead_score_range=[55, 69],
                lead_priority="medium",
                opportunity_stage="discovery",
                expected_route="standard_follow_up",
                should_write_crm=True,
                should_generate_tasks=True,
                required_task_titles=[],
                required_risk_flags=[],
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="should_generate_tasks"):
        load_golden_cases(path)
