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
    next_steps: list[str] | None = None,
) -> dict[str, object]:
    resolved_next_steps = ["发送正式报价单", "安排试点评审会"] if next_steps is None else next_steps
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
            "next_steps": resolved_next_steps,
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
        "manufacturing_complete_002",
        "enterprise_complete_001",
        "saas_complete_001",
        "healthcare_missing_002",
        "manufacturing_missing_001",
        "retail_missing_001",
        "retail_nurture_002",
        "finance_nurture_001",
        "education_nurture_001",
        "noise_002",
        "noise_003",
        "noise_004",
    ]
    assert by_case_id["high_intent_complete"]["expected_parse"]["account_name"] == "华东制造集团"
    assert by_case_id["high_intent_complete"]["segment"] == "high_intent_complete"
    assert by_case_id["high_intent_complete"]["expected_workflow"]["lead_priority"] == "high"
    assert by_case_id["high_intent_complete"]["expected_workflow"]["opportunity_stage"] == "proposal"
    assert by_case_id["high_intent_complete"]["expected_workflow"]["lead_score_range"] == [90, 100]
    assert by_case_id["high_intent_complete"]["expected_workflow"]["should_write_crm"] is True
    assert by_case_id["high_intent_complete"]["expected_workflow"]["should_generate_tasks"] is True
    assert by_case_id["high_intent_complete"]["expected_workflow"]["required_task_titles"] == [
        "发送正式报价单",
        "安排试点评审会",
    ]
    assert by_case_id["high_intent_complete"]["expected_workflow"]["required_risk_flags"] == []

    assert by_case_id["high_intent_missing_facts"]["expected_parse"]["account_name"] == "北区连锁零售"
    assert by_case_id["high_intent_missing_facts"]["segment"] == "high_intent_missing_facts"
    assert by_case_id["high_intent_missing_facts"]["expected_workflow"]["lead_priority"] == "high"
    assert by_case_id["high_intent_missing_facts"]["expected_workflow"]["opportunity_stage"] == "qualification"
    assert by_case_id["high_intent_missing_facts"]["expected_workflow"]["lead_score_range"] == [80, 89]
    assert by_case_id["high_intent_missing_facts"]["expected_workflow"]["should_write_crm"] is True
    assert by_case_id["high_intent_missing_facts"]["expected_workflow"]["should_generate_tasks"] is True
    assert by_case_id["high_intent_missing_facts"]["expected_workflow"]["required_task_titles"] == [
        "Clarify qualification gaps",
    ]
    assert by_case_id["high_intent_missing_facts"]["expected_parse"]["next_steps"] == [
        "补齐联系人信息",
        "确认预算范围",
    ]
    assert by_case_id["high_intent_missing_facts"]["expected_workflow"]["required_risk_flags"] == [
        "missing_required_facts"
    ]

    assert by_case_id["medium_intent_nurture"]["expected_parse"]["account_name"] == "南方科技服务公司"
    assert by_case_id["medium_intent_nurture"]["segment"] == "medium_intent_nurture"
    assert by_case_id["medium_intent_nurture"]["expected_workflow"]["lead_priority"] == "medium"
    assert by_case_id["medium_intent_nurture"]["expected_workflow"]["opportunity_stage"] == "discovery"
    assert by_case_id["medium_intent_nurture"]["expected_workflow"]["lead_score_range"] == [55, 69]
    assert by_case_id["medium_intent_nurture"]["expected_workflow"]["expected_route"] == "standard_follow_up"
    assert by_case_id["medium_intent_nurture"]["expected_workflow"]["should_write_crm"] is True
    assert by_case_id["medium_intent_nurture"]["expected_workflow"]["should_generate_tasks"] is True
    assert by_case_id["medium_intent_nurture"]["expected_workflow"]["required_task_titles"] == [
        "发送案例资料",
        "安排方案讲解",
    ]
    assert by_case_id["medium_intent_nurture"]["expected_workflow"]["required_risk_flags"] == []

    assert by_case_id["low_intent_or_noise"]["expected_parse"]["account_name"] == "未知"
    assert by_case_id["low_intent_or_noise"]["segment"] == "low_intent_or_noise"
    assert by_case_id["low_intent_or_noise"]["expected_workflow"]["lead_priority"] == "low"
    assert by_case_id["low_intent_or_noise"]["expected_workflow"]["opportunity_stage"] == "discovery"
    assert by_case_id["low_intent_or_noise"]["expected_workflow"]["lead_score_range"] == [0, 24]
    assert by_case_id["low_intent_or_noise"]["expected_workflow"]["should_write_crm"] is True
    assert by_case_id["low_intent_or_noise"]["expected_workflow"]["should_generate_tasks"] is False
    assert by_case_id["low_intent_or_noise"]["expected_workflow"]["required_task_titles"] == []
    assert by_case_id["low_intent_or_noise"]["expected_workflow"]["required_risk_flags"] == []

    assert by_case_id["manufacturing_complete_002"]["expected_parse"]["account_name"] == "Acme Robotics"
    assert by_case_id["manufacturing_complete_002"]["expected_workflow"]["lead_score_range"] == [80, 95]
    assert by_case_id["manufacturing_complete_002"]["expected_workflow"]["required_task_titles"] == [
        "run deployment workshop",
    ]

    assert by_case_id["enterprise_complete_001"]["expected_parse"]["account_name"] == "Northstar Logistics"
    assert by_case_id["enterprise_complete_001"]["expected_workflow"]["lead_score_range"] == [78, 92]
    assert by_case_id["enterprise_complete_001"]["expected_workflow"]["required_task_titles"] == [
        "send proposal",
    ]

    assert by_case_id["saas_complete_001"]["expected_parse"]["account_name"] == "Aurora SaaS"
    assert by_case_id["saas_complete_001"]["expected_workflow"]["lead_score_range"] == [78, 90]
    assert by_case_id["saas_complete_001"]["expected_workflow"]["required_task_titles"] == [
        "send statement of work",
    ]

    assert by_case_id["healthcare_missing_002"]["expected_parse"]["account_name"] == "BluePeak Health"
    assert by_case_id["healthcare_missing_002"]["expected_workflow"]["lead_score_range"] == [65, 80]
    assert by_case_id["healthcare_missing_002"]["expected_workflow"]["required_task_titles"] == [
        "Confirm budget range",
        "Confirm decision timeline",
    ]
    assert by_case_id["healthcare_missing_002"]["expected_workflow"]["required_risk_flags"] == [
        "missing_required_facts"
    ]

    assert by_case_id["manufacturing_missing_001"]["expected_parse"]["account_name"] == "Delta Machines"
    assert by_case_id["manufacturing_missing_001"]["expected_workflow"]["lead_score_range"] == [68, 82]
    assert by_case_id["manufacturing_missing_001"]["expected_workflow"]["required_task_titles"] == [
        "Identify decision makers",
        "Schedule qualification follow-up",
    ]
    assert by_case_id["manufacturing_missing_001"]["expected_workflow"]["required_risk_flags"] == [
        "missing_required_facts"
    ]

    assert by_case_id["retail_missing_001"]["expected_parse"]["account_name"] == "Harbor Retail Group"
    assert by_case_id["retail_missing_001"]["expected_workflow"]["lead_score_range"] == [62, 78]
    assert by_case_id["retail_missing_001"]["expected_workflow"]["required_task_titles"] == [
        "Confirm budget range",
        "Confirm decision timeline",
    ]
    assert by_case_id["retail_missing_001"]["expected_workflow"]["required_risk_flags"] == [
        "missing_required_facts"
    ]
    assert by_case_id["retail_nurture_002"]["expected_parse"]["account_name"] == "Northwind Traders"
    assert by_case_id["retail_nurture_002"]["expected_workflow"]["lead_priority"] == "low"
    assert by_case_id["retail_nurture_002"]["expected_workflow"]["opportunity_stage"] == "discovery"
    assert by_case_id["retail_nurture_002"]["expected_workflow"]["lead_score_range"] == [35, 49]
    assert by_case_id["retail_nurture_002"]["expected_workflow"]["expected_route"] == "low_priority_nurture"
    assert by_case_id["retail_nurture_002"]["expected_workflow"]["required_task_titles"] == []

    assert by_case_id["finance_nurture_001"]["expected_parse"]["account_name"] == "Meridian Finance"
    assert by_case_id["finance_nurture_001"]["expected_workflow"]["lead_priority"] == "low"
    assert by_case_id["finance_nurture_001"]["expected_workflow"]["lead_score_range"] == [35, 49]
    assert by_case_id["finance_nurture_001"]["expected_workflow"]["expected_route"] == "low_priority_nurture"

    assert by_case_id["education_nurture_001"]["expected_parse"]["account_name"] == "Summit Education"
    assert by_case_id["education_nurture_001"]["expected_workflow"]["lead_priority"] == "low"
    assert by_case_id["education_nurture_001"]["expected_workflow"]["lead_score_range"] == [35, 49]
    assert by_case_id["education_nurture_001"]["expected_workflow"]["expected_route"] == "low_priority_nurture"

    assert by_case_id["noise_002"]["expected_parse"]["account_name"] == "Orchard Foods"
    assert by_case_id["noise_002"]["expected_workflow"]["lead_score_range"] == [0, 35]
    assert by_case_id["noise_002"]["expected_workflow"]["expected_route"] == "low_priority_nurture"

    assert by_case_id["noise_003"]["expected_parse"]["account_name"] == "Atlas Print"
    assert by_case_id["noise_003"]["expected_workflow"]["lead_score_range"] == [0, 35]

    assert by_case_id["noise_004"]["expected_parse"]["account_name"] == "Pineview Hotels"
    assert by_case_id["noise_004"]["expected_workflow"]["lead_score_range"] == [0, 35]

    for case in cases:
        allowed_missing_fact_titles = {
            "Confirm budget range",
            "Confirm decision timeline",
            "Identify decision makers",
            "Schedule qualification follow-up",
            "Clarify qualification gaps",
        }
        for title in case["expected_workflow"]["required_task_titles"]:
            assert title in case["expected_parse"]["next_steps"] or title in allowed_missing_fact_titles


def test_load_golden_cases_allows_medium_nurture_need_more_info_route(tmp_path):
    path = tmp_path / "medium_need_more_info.jsonl"
    path.write_text(
        json.dumps(
            {
                "case_id": "medium_need_more_info",
                "segment": "medium_intent_nurture",
                "customer_profile_text": "Account: Contoso Widgets\nIndustry: Manufacturing\nCurrent stage: Discovery",
                "meeting_note_text": "The buyer wants to revisit once they have enough internal context.",
                "expected_parse": {
                    "account_name": "Contoso Widgets",
                    "customer_roles": [],
                    "confirmed_needs": [],
                    "budget_signals": [],
                    "timeline_signals": [],
                    "next_steps": [],
                    "competitors": [],
                },
                "expected_workflow": {
                    "lead_score_range": [55, 69],
                    "lead_priority": "medium",
                    "opportunity_stage": "discovery",
                    "expected_route": "need_more_info",
                    "should_write_crm": True,
                    "should_generate_tasks": False,
                    "required_task_titles": [],
                    "required_risk_flags": [],
                },
            }
        ),
        encoding="utf-8",
    )

    cases = load_golden_cases(path)

    assert cases[0]["expected_workflow"]["expected_route"] == "need_more_info"
def test_load_golden_cases_raises_when_medium_nurture_need_more_info_has_normal_content(tmp_path):
    path = tmp_path / "medium_need_more_info_normal_content.jsonl"
    path.write_text(
        json.dumps(
            _build_sales_case(
                "medium_need_more_info_normal_content",
                segment="medium_intent_nurture",
                lead_score_range=[55, 69],
                lead_priority="medium",
                opportunity_stage="discovery",
                expected_route="need_more_info",
                should_write_crm=True,
                should_generate_tasks=False,
                required_task_titles=[],
                required_risk_flags=[],
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="need_more_info requires empty structured fields"):
        load_golden_cases(path)


def test_load_golden_cases_raises_when_medium_nurture_need_more_info_uses_high_priority(tmp_path):
    path = tmp_path / "medium_need_more_info_high_priority.jsonl"
    path.write_text(
        json.dumps(
            _build_sales_case(
                "medium_need_more_info_high_priority",
                segment="medium_intent_nurture",
                lead_score_range=[55, 69],
                lead_priority="high",
                opportunity_stage="discovery",
                expected_route="need_more_info",
                should_write_crm=True,
                should_generate_tasks=False,
                required_task_titles=[],
                required_risk_flags=[],
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="lead_priority"):
        load_golden_cases(path)


def test_golden_case_file_has_unique_ids_and_balanced_segment_coverage():
    cases = load_golden_cases(Path(__file__).resolve().parents[2] / "evals" / "sales_copilot" / "golden_cases.jsonl")

    case_ids = [case["case_id"] for case in cases]
    segments = [case["segment"] for case in cases]

    assert len(cases) == 16
    assert len(case_ids) == len(set(case_ids))
    assert segments.count("high_intent_complete") == 4
    assert segments.count("high_intent_missing_facts") == 4
    assert segments.count("medium_intent_nurture") == 4
    assert segments.count("low_intent_or_noise") == 4


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
                lead_score_range=[80, 89],
                lead_priority="high",
                opportunity_stage="qualification",
                expected_route="high_priority_follow_up",
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


def test_load_golden_cases_raises_when_high_priority_route_has_no_score_overlap(tmp_path):
    path = tmp_path / "no_overlap_high_priority.jsonl"
    path.write_text(
        json.dumps(
            _build_sales_case(
                "no_overlap_high_priority",
                segment="high_intent_complete",
                lead_score_range=[78, 79],
                lead_priority="high",
                opportunity_stage="proposal",
                expected_route="high_priority_follow_up",
                should_write_crm=True,
                should_generate_tasks=True,
                required_task_titles=["send proposal"],
                required_risk_flags=[],
                next_steps=["send proposal"],
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="overlap"):
        load_golden_cases(path)


def test_load_golden_cases_raises_when_standard_route_has_no_score_overlap(tmp_path):
    path = tmp_path / "no_overlap_standard.jsonl"
    path.write_text(
        json.dumps(
            _build_sales_case(
                "no_overlap_standard",
                segment="high_intent_missing_facts",
                lead_score_range=[81, 90],
                lead_priority="high",
                opportunity_stage="qualification",
                expected_route="standard_follow_up",
                should_write_crm=True,
                should_generate_tasks=True,
                required_task_titles=["Confirm budget range"],
                required_risk_flags=["missing_required_facts"],
                next_steps=[],
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="overlap"):
        load_golden_cases(path)


def test_load_golden_cases_raises_when_route_spillover_is_too_wide(tmp_path):
    path = tmp_path / "too_wide_spillover.jsonl"
    path.write_text(
        json.dumps(
            _build_sales_case(
                "too_wide_spillover",
                segment="high_intent_missing_facts",
                lead_score_range=[50, 100],
                lead_priority="high",
                opportunity_stage="qualification",
                expected_route="standard_follow_up",
                should_write_crm=True,
                should_generate_tasks=True,
                required_task_titles=["Clarify qualification gaps"],
                required_risk_flags=["missing_required_facts"],
                next_steps=["Clarify qualification gaps"],
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="overlap"):
        load_golden_cases(path)


def test_load_golden_cases_allows_spillover_of_three_points(tmp_path):
    path = tmp_path / "spillover_three.jsonl"
    path.write_text(
        json.dumps(
            _build_sales_case(
                "spillover_three",
                segment="high_intent_missing_facts",
                lead_score_range=[50, 82],
                lead_priority="high",
                opportunity_stage="qualification",
                expected_route="standard_follow_up",
                should_write_crm=True,
                should_generate_tasks=True,
                required_task_titles=["Confirm budget range"],
                required_risk_flags=["missing_required_facts"],
                next_steps=[],
            )
        ),
        encoding="utf-8",
    )

    cases = load_golden_cases(path)

    assert cases[0]["expected_workflow"]["lead_score_range"] == [50, 82]
    assert cases[0]["expected_parse"]["next_steps"] == []


def test_load_golden_cases_allows_two_sided_spillover_within_limit(tmp_path):
    path = tmp_path / "spillover_two_sided.jsonl"
    path.write_text(
        json.dumps(
            _build_sales_case(
                "spillover_two_sided",
                segment="high_intent_missing_facts",
                lead_score_range=[49, 81],
                lead_priority="high",
                opportunity_stage="qualification",
                expected_route="standard_follow_up",
                should_write_crm=True,
                should_generate_tasks=True,
                required_task_titles=["Confirm budget range"],
                required_risk_flags=["missing_required_facts"],
                next_steps=[],
            )
        ),
        encoding="utf-8",
    )

    cases = load_golden_cases(path)

    assert cases[0]["expected_workflow"]["lead_score_range"] == [49, 81]
    assert cases[0]["expected_parse"]["next_steps"] == []


def test_load_golden_cases_raises_when_spillover_exceeds_three_points(tmp_path):
    path = tmp_path / "spillover_four.jsonl"
    path.write_text(
        json.dumps(
            _build_sales_case(
                "spillover_four",
                segment="high_intent_missing_facts",
                lead_score_range=[50, 83],
                lead_priority="high",
                opportunity_stage="qualification",
                expected_route="standard_follow_up",
                should_write_crm=True,
                should_generate_tasks=True,
                required_task_titles=["Confirm budget range"],
                required_risk_flags=["missing_required_facts"],
                next_steps=[],
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="overlap"):
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


def test_load_golden_cases_raises_when_required_task_titles_are_not_next_steps_subset(tmp_path):
    path = tmp_path / "bad_task_subset.jsonl"
    path.write_text(
        json.dumps(
            _build_sales_case(
                "bad_task_subset",
                segment="medium_intent_nurture",
                lead_score_range=[55, 69],
                lead_priority="medium",
                opportunity_stage="discovery",
                expected_route="standard_follow_up",
                should_write_crm=True,
                should_generate_tasks=True,
                required_task_titles=["额外追问"],
                required_risk_flags=[],
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="required_task_titles"):
        load_golden_cases(path)


def test_load_golden_cases_raises_when_medium_nurture_pair_is_mismatched_to_route(tmp_path):
    path = tmp_path / "bad_medium_nurture_pair_route.jsonl"
    path.write_text(
        json.dumps(
            _build_sales_case(
                "bad_medium_nurture_pair_route",
                segment="medium_intent_nurture",
                lead_score_range=[35, 49],
                lead_priority="medium",
                opportunity_stage="discovery",
                expected_route="low_priority_nurture",
                should_write_crm=True,
                should_generate_tasks=False,
                required_task_titles=[],
                required_risk_flags=[],
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="allowed lead_priority/expected_route combinations"):
        load_golden_cases(path)


def test_load_golden_cases_raises_when_medium_nurture_pair_is_mismatched_to_priority(tmp_path):
    path = tmp_path / "bad_medium_nurture_pair_priority.jsonl"
    path.write_text(
        json.dumps(
            _build_sales_case(
                "bad_medium_nurture_pair_priority",
                segment="medium_intent_nurture",
                lead_score_range=[55, 69],
                lead_priority="low",
                opportunity_stage="discovery",
                expected_route="standard_follow_up",
                should_write_crm=True,
                should_generate_tasks=False,
                required_task_titles=[],
                required_risk_flags=[],
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="allowed lead_priority/expected_route combinations"):
        load_golden_cases(path)


def test_load_golden_cases_raises_when_segment_contract_is_inconsistent(tmp_path):
    path = tmp_path / "bad_segment_contract.jsonl"
    path.write_text(
        json.dumps(
            _build_sales_case(
                "bad_segment_contract",
                segment="high_intent_missing_facts",
                lead_score_range=[55, 69],
                lead_priority="medium",
                opportunity_stage="qualification",
                expected_route="standard_follow_up",
                should_write_crm=True,
                should_generate_tasks=True,
                required_task_titles=["补齐联系人信息"],
                required_risk_flags=["missing_required_facts"],
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="segment"):
        load_golden_cases(path)


def test_load_golden_cases_raises_when_missing_required_facts_appears_in_other_segments(tmp_path):
    path = tmp_path / "bad_missing_required_facts_segment.jsonl"
    path.write_text(
        json.dumps(
            _build_sales_case(
                "bad_missing_required_facts_segment",
                segment="medium_intent_nurture",
                lead_score_range=[55, 69],
                lead_priority="medium",
                opportunity_stage="discovery",
                expected_route="standard_follow_up",
                should_write_crm=True,
                should_generate_tasks=True,
                required_task_titles=["发送案例资料"],
                required_risk_flags=["missing_required_facts"],
                next_steps=["发送案例资料"],
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing_required_facts"):
        load_golden_cases(path)
