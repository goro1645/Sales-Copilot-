from evals.sales_copilot.metrics import evaluate_parse_case, summarize_parse_metrics


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


def test_summarize_parse_metrics_aggregates_json_validity_and_average_f1():
    rows = [
        {
            "json_valid": True,
            "field_exact_match": {"account_name": True},
            "list_field_f1": {
                "customer_roles": 1.0,
                "confirmed_needs": 1.0,
                "budget_signals": 1.0,
                "timeline_signals": 1.0,
                "next_steps": 1.0,
                "competitors": 1.0,
            },
            "risk_flag_recall": 1.0,
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
            "risk_flag_recall": 0.0,
        },
    ]

    summary = summarize_parse_metrics(rows)

    assert summary["json_valid_rate"] == 0.5
    assert summary["field_exact_match_rate"]["account_name"] == 0.5
    assert summary["average_list_field_f1"] == 0.5
    assert summary["risk_flag_recall"] == 0.5
