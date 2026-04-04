import json

import pytest

from evals.sales_copilot.cases import load_golden_cases


def _build_sales_case(case_id: str, expected_workflow: dict[str, object]) -> dict[str, object]:
    return {
        "case_id": case_id,
        "input_text": "客户在本周会议中明确表达采购意向，并希望尽快确认试点方案。",
        "expected_parse": {
            "account_name": "华东制造集团",
            "customer_roles": ["采购负责人", "业务总监"],
            "confirmed_needs": ["试点方案", "报价单"],
            "budget_signals": ["已有年度预算", "预算已预留"],
            "timeline_signals": ["本周确认", "下周推进试点"],
            "next_steps": ["发正式方案", "安排试点评审会"],
            "competitors": ["竞品A"],
        },
        "expected_workflow": expected_workflow,
    }


def test_load_golden_cases_reads_two_jsonl_records_with_full_contract(tmp_path):
    path = tmp_path / "golden_cases.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    _build_sales_case(
                        "high_intent_complete",
                        {
                            "lead_score_range": [85, 100],
                            "lead_priority": "P0",
                            "opportunity_stage": "qualified",
                            "expected_route": "complete",
                            "should_write_crm": True,
                            "should_generate_tasks": True,
                            "required_task_titles": ["发送报价单", "安排试点评审"],
                            "required_risk_flags": ["预算待确认"],
                        },
                    )
                ),
                json.dumps(
                    _build_sales_case(
                        "medium_intent_nurture",
                        {
                            "lead_score_range": [55, 69],
                            "lead_priority": "P2",
                            "opportunity_stage": "nurture",
                            "expected_route": "nurture",
                            "should_write_crm": False,
                            "should_generate_tasks": True,
                            "required_task_titles": ["补充联系人信息", "发送案例资料"],
                            "required_risk_flags": ["决策链未明确"],
                        },
                    )
                ),
            ]
        ),
        encoding="utf-8",
    )

    cases = load_golden_cases(path)

    assert [case["case_id"] for case in cases] == [
        "high_intent_complete",
        "medium_intent_nurture",
    ]
    assert cases[0]["expected_parse"]["account_name"] == "华东制造集团"
    assert cases[0]["expected_parse"]["customer_roles"] == ["采购负责人", "业务总监"]
    assert cases[0]["expected_workflow"]["expected_route"] == "complete"
    assert cases[1]["expected_workflow"]["required_task_titles"] == [
        "补充联系人信息",
        "发送案例资料",
    ]


def test_load_golden_cases_raises_when_required_workflow_fields_missing(tmp_path):
    path = tmp_path / "invalid_golden_cases.jsonl"
    path.write_text(
        json.dumps(
            _build_sales_case(
                "broken_case",
                    {
                        "lead_score_range": [10, 25],
                        "lead_priority": "P4",
                        "opportunity_stage": "ignored",
                        "expected_route": "ignore",
                        "should_write_crm": False,
                        "should_generate_tasks": False,
                        "required_risk_flags": ["噪音线索"],
                    },
                )
            ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="required_workflow_fields"):
        load_golden_cases(path)
