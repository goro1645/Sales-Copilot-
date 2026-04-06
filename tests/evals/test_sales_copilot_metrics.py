from evals.sales_copilot.metrics import (
    evaluate_parse_case,
    evaluate_workflow_case,
    summarize_parse_metrics,
    summarize_workflow_metrics,
)


def test_evaluate_parse_case_scores_scalar_and_list_fields():
    case = {
        "expected_parse": {
            "account_name": "BluePeak Health",
            "customer_roles": ["CIO", "Compliance Manager"],
            "confirmed_needs": ["private deployment", "audit logging"],
            "budget_signals": ["pilot approved"],
            "timeline_signals": [],
            "next_steps": ["schedule workshop"],
            "competitors": [],
        },
        "expected_workflow": {"required_risk_flags": ["missing_required_facts"]},
    }
    actual_parse = {
        "account_name": "BluePeak Health",
        "customer_roles": ["CIO"],
        "confirmed_needs": ["private deployment", "audit logging"],
        "budget_signals": ["pilot approved"],
        "timeline_signals": [],
        "next_steps": ["schedule workshop", "send recap"],
        "competitors": [],
        "risk_flags": ["missing_required_facts", "needs_follow_up"],
    }

    metrics = evaluate_parse_case(case, actual_parse)

    assert metrics["json_valid"] is True
    assert metrics["field_exact_match"]["account_name"] is True
    assert metrics["list_field_precision"]["customer_roles"] == 1.0
    assert metrics["list_field_recall"]["customer_roles"] == 0.5
    assert metrics["list_field_f1"]["customer_roles"] == 2 / 3
    assert metrics["list_field_f1"]["confirmed_needs"] == 1.0
    assert metrics["risk_flag_recall"] == 1.0


def test_evaluate_parse_case_treats_non_exact_account_name_as_mismatch():
    case = {
        "expected_parse": {
            "account_name": "BluePeak Health",
            "customer_roles": [],
            "confirmed_needs": [],
            "budget_signals": [],
            "timeline_signals": [],
            "next_steps": [],
            "competitors": [],
        },
        "expected_workflow": {"required_risk_flags": []},
    }
    actual_parse = {
        "account_name": " bluepeak health ",
        "customer_roles": [],
        "confirmed_needs": [],
        "budget_signals": [],
        "timeline_signals": [],
        "next_steps": [],
        "competitors": [],
        "risk_flags": [],
    }

    metrics = evaluate_parse_case(case, actual_parse)

    assert metrics["field_exact_match"]["account_name"] is False


def test_evaluate_parse_case_marks_invalid_json_as_zeroed_metrics():
    case = {
        "expected_parse": {
            "account_name": "BluePeak Health",
            "customer_roles": ["CIO"],
            "confirmed_needs": ["private deployment"],
            "budget_signals": ["pilot approved"],
            "timeline_signals": [],
            "next_steps": ["schedule workshop"],
            "competitors": [],
        },
        "expected_workflow": {"required_risk_flags": ["missing_required_facts"]},
    }

    metrics = evaluate_parse_case(case, ["not", "a", "dict"])

    assert metrics["json_valid"] is False
    assert metrics["field_exact_match"]["account_name"] == 0
    assert metrics["list_field_precision"]["customer_roles"] == 0
    assert metrics["list_field_recall"]["customer_roles"] == 0
    assert metrics["list_field_f1"]["customer_roles"] == 0
    assert metrics["risk_flag_recall"] == 0


def test_evaluate_parse_case_marks_malformed_list_schema_as_invalid():
    case = {
        "expected_parse": {
            "account_name": "BluePeak Health",
            "customer_roles": ["CIO"],
            "confirmed_needs": [],
            "budget_signals": [],
            "timeline_signals": [],
            "next_steps": [],
            "competitors": [],
        },
        "expected_workflow": {"required_risk_flags": []},
    }
    actual_parse = {
        "account_name": "BluePeak Health",
        "customer_roles": "CIO",
        "confirmed_needs": [],
        "budget_signals": [],
        "timeline_signals": [],
        "next_steps": [],
        "competitors": [],
        "risk_flags": [],
    }

    metrics = evaluate_parse_case(case, actual_parse)

    assert metrics["json_valid"] is False
    assert metrics["list_field_f1"]["customer_roles"] == 0


def test_summarize_parse_metrics_aggregates_json_validity_and_average_f1():
    rows = [
        {
            "json_valid": True,
            "field_exact_match": {"account_name": True},
            "list_field_f1": {
                "customer_roles": 1.0,
                "confirmed_needs": 1.0,
                "budget_signals": 0.0,
                "timeline_signals": 0.0,
                "next_steps": 0.0,
                "competitors": 0.0,
            },
            "list_field_applicable": {
                "customer_roles": True,
                "confirmed_needs": True,
                "budget_signals": False,
                "timeline_signals": False,
                "next_steps": False,
                "competitors": False,
            },
            "risk_flag_recall": 1.0,
            "risk_flag_applicable": True,
        },
        {
            "json_valid": False,
            "field_exact_match": {"account_name": False},
            "list_field_f1": {
                "customer_roles": 0.0,
                "confirmed_needs": 0.0,
                "budget_signals": 0.0,
                "timeline_signals": 0.0,
                "next_steps": 0.0,
                "competitors": 0.0,
            },
            "list_field_applicable": {
                "customer_roles": True,
                "confirmed_needs": True,
                "budget_signals": False,
                "timeline_signals": False,
                "next_steps": False,
                "competitors": False,
            },
            "risk_flag_recall": 0.0,
            "risk_flag_applicable": True,
        },
    ]

    summary = summarize_parse_metrics(rows)

    assert summary["json_valid_rate"] == 0.5
    assert summary["field_exact_match_rate"]["account_name"] == 0.5
    assert summary["average_list_field_f1"] == 0.5
    assert summary["risk_flag_recall"] == 0.5


def test_summarize_parse_metrics_ignores_non_applicable_risk_flags():
    rows = [
        {
            "json_valid": True,
            "field_exact_match": {"account_name": True},
            "list_field_f1": {field: 0.0 for field in ("customer_roles", "confirmed_needs", "budget_signals", "timeline_signals", "next_steps", "competitors")},
            "list_field_applicable": {field: False for field in ("customer_roles", "confirmed_needs", "budget_signals", "timeline_signals", "next_steps", "competitors")},
            "risk_flag_recall": 0.0,
            "risk_flag_applicable": False,
        },
        {
            "json_valid": True,
            "field_exact_match": {"account_name": True},
            "list_field_f1": {field: 0.0 for field in ("customer_roles", "confirmed_needs", "budget_signals", "timeline_signals", "next_steps", "competitors")},
            "list_field_applicable": {field: False for field in ("customer_roles", "confirmed_needs", "budget_signals", "timeline_signals", "next_steps", "competitors")},
            "risk_flag_recall": 1.0,
            "risk_flag_applicable": True,
        },
    ]

    summary = summarize_parse_metrics(rows)

    assert summary["risk_flag_recall"] == 1.0


def test_summarize_parse_metrics_ignores_empty_list_fields_in_average():
    rows = [
        {
            "json_valid": True,
            "field_exact_match": {"account_name": True},
            "list_field_f1": {
                "customer_roles": 0.0,
                "confirmed_needs": 0.0,
                "budget_signals": 0.0,
                "timeline_signals": 0.0,
                "next_steps": 0.0,
                "competitors": 0.0,
            },
            "list_field_applicable": {
                "customer_roles": True,
                "confirmed_needs": False,
                "budget_signals": False,
                "timeline_signals": False,
                "next_steps": False,
                "competitors": False,
            },
            "risk_flag_recall": 0.0,
            "risk_flag_applicable": False,
        }
    ]

    summary = summarize_parse_metrics(rows)

    assert summary["average_list_field_f1"] == 0.0


def test_summarize_parse_metrics_includes_invalid_rows_when_gold_fields_are_applicable():
    case = {
        "expected_parse": {
            "account_name": "BluePeak Health",
            "customer_roles": ["CIO"],
            "confirmed_needs": [],
            "budget_signals": [],
            "timeline_signals": [],
            "next_steps": [],
            "competitors": [],
        },
        "expected_workflow": {"required_risk_flags": ["missing_required_facts"]},
    }
    valid_actual_parse = {
        "account_name": "BluePeak Health",
        "customer_roles": ["CIO"],
        "confirmed_needs": [],
        "budget_signals": [],
        "timeline_signals": [],
        "next_steps": [],
        "competitors": [],
        "risk_flags": ["missing_required_facts"],
    }
    malformed_actual_parse = {
        "account_name": "BluePeak Health",
        "customer_roles": "CIO",
        "confirmed_needs": [],
        "budget_signals": [],
        "timeline_signals": [],
        "next_steps": [],
        "competitors": [],
        "risk_flags": [],
    }

    valid_row = evaluate_parse_case(case, valid_actual_parse)
    malformed_row = evaluate_parse_case(case, malformed_actual_parse)

    assert valid_row["json_valid"] is True
    assert malformed_row["json_valid"] is False
    assert malformed_row["list_field_applicable"]["customer_roles"] is True
    assert malformed_row["risk_flag_applicable"] is True

    summary = summarize_parse_metrics([valid_row, malformed_row])

    assert summary["json_valid_rate"] == 0.5
    assert summary["average_list_field_f1"] == 0.5
    assert summary["risk_flag_recall"] == 0.5


def test_evaluate_workflow_case_scores_route_score_crm_and_tasks():
    case = {
        "expected_workflow": {
            "lead_score_range": [50, 79],
            "lead_priority": "medium",
            "opportunity_stage": "qualification",
            "expected_route": "standard_follow_up",
            "should_write_crm": True,
            "should_generate_tasks": True,
            "required_task_titles": ["Schedule workshop"],
            "required_risk_flags": [],
        }
    }
    actual_result = {
        "workflow_log": [
            {"event": "route_decided", "route": "standard_follow_up"},
            {"event": "task_created", "task_title": "Schedule workshop"},
        ],
        "score": 72,
        "priority": "medium",
        "stage": "qualification",
        "crm_writeback": True,
        "task_payload": [
            {"title": "Schedule workshop"},
            {"title": "Send recap"},
        ],
    }

    metrics = evaluate_workflow_case(case, actual_result)

    assert metrics["workflow_success"] is True
    assert metrics["route_correct"] is True
    assert metrics["priority_correct"] is True
    assert metrics["stage_correct"] is True
    assert metrics["score_in_range"] is True
    assert metrics["crm_writeback_correct"] is True
    assert metrics["task_generation_correct"] is True
    assert metrics["required_task_hit_rate"] == 1.0


def test_summarize_workflow_metrics_aggregates_success_route_and_required_task_hit_rate():
    rows = [
        {
            "workflow_success": True,
            "route_correct": True,
            "priority_correct": True,
            "stage_correct": True,
            "score_in_range": True,
            "crm_writeback_correct": True,
            "task_generation_correct": True,
            "required_task_hit_rate": 1.0,
            "required_task_applicable": True,
        },
        {
            "workflow_success": False,
            "route_correct": False,
            "priority_correct": True,
            "stage_correct": True,
            "score_in_range": True,
            "crm_writeback_correct": True,
            "task_generation_correct": False,
            "required_task_hit_rate": 0.0,
            "required_task_applicable": True,
        },
    ]

    summary = summarize_workflow_metrics(rows)

    assert summary["workflow_success_rate"] == 0.5
    assert summary["route_accuracy"] == 0.5
    assert summary["priority_accuracy"] == 1.0
    assert summary["stage_accuracy"] == 1.0
    assert summary["score_range_accuracy"] == 1.0
    assert summary["crm_writeback_accuracy"] == 1.0
    assert summary["task_generation_hit_rate"] == 0.5
    assert summary["required_task_hit_rate"] == 0.5
