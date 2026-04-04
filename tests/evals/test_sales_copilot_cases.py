import json
import re
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

    assert [case["case_id"] for case in cases] == [
        "high_intent_complete",
        "high_intent_missing_facts",
        "medium_intent_nurture",
        "low_intent_or_noise",
    ]
    assert {case["segment"] for case in cases} == {
        "high_intent_complete",
        "high_intent_missing_facts",
        "medium_intent_nurture",
        "low_intent_or_noise",
    }
    assert {case["expected_workflow"]["expected_route"] for case in cases} == {
        "high_priority_follow_up",
        "standard_follow_up",
        "low_priority_nurture",
    }
    assert {case["expected_workflow"]["lead_priority"] for case in cases} == {
        "low",
        "medium",
        "high",
    }
    assert cases[0]["customer_profile_text"].startswith("华东制造集团")
    assert cases[0]["meeting_note_text"].startswith("客户明确表示本周要确认报价")


def test_load_golden_cases_raises_when_segment_is_invalid(tmp_path):
    path = tmp_path / "invalid_segment.jsonl"
    path.write_text(
        json.dumps(
            _build_sales_case(
                "bad_segment",
                segment="enterprise",
                lead_score_range=[90, 100],
                lead_priority="high",
                opportunity_stage="proposal",
                expected_route="high_priority_follow_up",
                should_write_crm=True,
                should_generate_tasks=True,
                required_task_titles=["发送正式报价单"],
                required_risk_flags=["missing_required_facts"],
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="segment"):
        load_golden_cases(path)


def test_load_golden_cases_raises_when_risk_flag_is_not_snake_case(tmp_path):
    path = tmp_path / "invalid_risk_flag.jsonl"
    path.write_text(
        json.dumps(
            _build_sales_case(
                "bad_risk_flag",
                segment="medium_intent_nurture",
                lead_score_range=[90, 100],
                lead_priority="high",
                opportunity_stage="proposal",
                expected_route="high_priority_follow_up",
                should_write_crm=True,
                should_generate_tasks=True,
                required_task_titles=["发送正式报价单"],
                required_risk_flags=["预算待确认"],
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="required_risk_flags"):
        load_golden_cases(path)


def test_load_golden_cases_raises_when_tasks_are_disabled_but_titles_exist(tmp_path):
    path = tmp_path / "invalid_task_contract.jsonl"
    path.write_text(
        json.dumps(
            _build_sales_case(
                "bad_task_contract",
                segment="low_intent_or_noise",
                lead_score_range=[0, 24],
                lead_priority="low",
                opportunity_stage="discovery",
                expected_route="low_priority_nurture",
                should_write_crm=True,
                should_generate_tasks=False,
                required_task_titles=["发送跟进邮件"],
                required_risk_flags=[],
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="should_generate_tasks"):
        load_golden_cases(path)
