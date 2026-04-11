from unittest.mock import patch

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


def test_evaluate_parse_case_allows_loose_list_value_matching():
    case = {
        "expected_parse": {
            "account_name": "GSSi, Inc.",
            "customer_roles": ["Councilmember"],
            "confirmed_needs": ["contract extension"],
            "budget_signals": ["not to exceed 999900"],
            "timeline_signals": ["hold to next meeting"],
            "next_steps": ["review pricing assumptions"],
            "competitors": [],
        },
        "expected_workflow": {"required_risk_flags": []},
    }
    actual_parse = {
        "account_name": "GSSi, Inc.",
        "customer_roles": ["council member"],
        "confirmed_needs": ["extend contract term to March 9, 2020"],
        "budget_signals": ["revised total not to exceed $999,900"],
        "timeline_signals": ["move item back one week"],
        "next_steps": ["prepare detailed pricing review"],
        "competitors": [],
        "risk_flags": [],
    }

    metrics = evaluate_parse_case(case, actual_parse)

    assert metrics["list_field_f1"]["customer_roles"] == 1.0
    assert metrics["list_field_f1"]["budget_signals"] == 1.0
    assert metrics["list_field_f1"]["timeline_signals"] == 1.0
    assert metrics["list_field_f1"]["next_steps"] == 1.0


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
            "list_field_precision": {
                "customer_roles": 1.0,
                "confirmed_needs": 1.0,
                "budget_signals": 0.0,
                "timeline_signals": 0.0,
                "next_steps": 0.0,
                "competitors": 0.0,
            },
            "list_field_recall": {
                "customer_roles": 1.0,
                "confirmed_needs": 1.0,
                "budget_signals": 0.0,
                "timeline_signals": 0.0,
                "next_steps": 0.0,
                "competitors": 0.0,
            },
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
            "list_field_precision": {
                "customer_roles": 0.0,
                "confirmed_needs": 0.0,
                "budget_signals": 0.0,
                "timeline_signals": 0.0,
                "next_steps": 0.0,
                "competitors": 0.0,
            },
            "list_field_recall": {
                "customer_roles": 0.0,
                "confirmed_needs": 0.0,
                "budget_signals": 0.0,
                "timeline_signals": 0.0,
                "next_steps": 0.0,
                "competitors": 0.0,
            },
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
    assert summary["list_field_precision"] == 0.5
    assert summary["list_field_recall"] == 0.5
    assert summary["list_field_f1"] == 0.5
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


def test_evaluate_parse_case_adds_semantic_match_for_paraphrases():
    case = {
        "expected_parse": {
            "account_name": "BluePeak Health",
            "customer_roles": [],
            "confirmed_needs": ["need private deployment with audit trail"],
            "budget_signals": [],
            "timeline_signals": [],
            "next_steps": ["follow up after carrier review"],
            "competitors": [],
        },
        "expected_workflow": {"required_risk_flags": []},
    }
    actual_parse = {
        "account_name": "BluePeak Health",
        "customer_roles": [],
        "confirmed_needs": ["wants on-prem deployment and audit logging"],
        "budget_signals": [],
        "timeline_signals": [],
        "next_steps": ["contact carrier, verify issue, then reply"],
        "competitors": [],
        "risk_flags": [],
    }

    fake_vectors = {
        "need private deployment with audit trail": [1.0, 0.0],
        "wants on-prem deployment and audit logging": [0.99, 0.01],
        "follow up after carrier review": [0.0, 1.0],
        "contact carrier, verify issue, then reply": [0.0, 0.99],
    }

    class _FakeEmbedder:
        model_name = "fake-semantic"

        def embed_texts(self, texts):
            return [fake_vectors[text] for text in texts]

    with patch("evals.sales_copilot.metrics.load_default_embedder", return_value=_FakeEmbedder()):
        metrics = evaluate_parse_case(case, actual_parse)

    assert metrics["semantic_list_field_f1"]["confirmed_needs"] == 1.0
    assert metrics["semantic_list_field_f1"]["next_steps"] == 1.0


def test_evaluate_parse_case_semantic_guards_block_cross_field_false_positive():
    case = {
        "expected_parse": {
            "account_name": "BluePeak Health",
            "customer_roles": [],
            "confirmed_needs": [],
            "budget_signals": ["refund coupon difference"],
            "timeline_signals": [],
            "next_steps": [],
            "competitors": [],
        },
        "expected_workflow": {"required_risk_flags": []},
    }
    actual_parse = {
        "account_name": "BluePeak Health",
        "customer_roles": [],
        "confirmed_needs": [],
        "budget_signals": ["contact support tomorrow"],
        "timeline_signals": [],
        "next_steps": [],
        "competitors": [],
        "risk_flags": [],
    }

    fake_vectors = {
        "refund coupon difference": [1.0, 0.0],
        "contact support tomorrow": [1.0, 0.0],
    }

    class _FakeEmbedder:
        model_name = "fake-semantic"

        def embed_texts(self, texts):
            return [fake_vectors[text] for text in texts]

    with patch("evals.sales_copilot.metrics.load_default_embedder", return_value=_FakeEmbedder()):
        metrics = evaluate_parse_case(case, actual_parse)

    assert metrics["semantic_list_field_recall"]["budget_signals"] == 0.0


def test_summarize_parse_metrics_includes_semantic_summary_values():
    fields = ("customer_roles", "confirmed_needs", "budget_signals", "timeline_signals", "next_steps", "competitors")
    rows = [
        {
            "json_valid": True,
            "field_exact_match": {"account_name": True},
            "list_field_precision": {field: 0.0 for field in fields},
            "list_field_recall": {field: 0.0 for field in fields},
            "list_field_f1": {field: 0.0 for field in fields},
            "semantic_list_field_precision": {field: (1.0 if field == "confirmed_needs" else 0.0) for field in fields},
            "semantic_list_field_recall": {field: (1.0 if field == "confirmed_needs" else 0.0) for field in fields},
            "semantic_list_field_f1": {field: (1.0 if field == "confirmed_needs" else 0.0) for field in fields},
            "list_field_applicable": {field: field == "confirmed_needs" for field in fields},
            "semantic_list_field_applicable": {field: field == "confirmed_needs" for field in fields},
            "risk_flag_recall": 0.0,
            "risk_flag_applicable": False,
        }
    ]

    summary = summarize_parse_metrics(rows)

    assert summary["semantic_list_field_precision"] == 1.0
    assert summary["semantic_list_field_recall"] == 1.0
    assert summary["semantic_list_field_f1"] == 1.0
    assert summary["average_semantic_list_field_f1"] == 1.0


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


def test_evaluate_workflow_case_uses_real_runner_fields():
    case = {
        "expected_workflow": {
            "lead_score_range": [80, 100],
            "lead_priority": "high",
            "opportunity_stage": "proposal",
            "expected_route": "high_priority_follow_up",
            "should_write_crm": True,
            "should_generate_tasks": True,
            "required_task_titles": ["Prepare workshop"],
            "required_risk_flags": [],
        }
    }
    actual_result = {
        "workflow_log": [{"route": "high_priority_follow_up"}],
        "lead_score": 92,
        "lead_priority": "high",
        "opportunity_stage": "proposal",
        "crm_update_ids": ["crm-1", "crm-2"],
        "task_payload": [{"title": "Prepare workshop agenda"}],
    }

    metrics = evaluate_workflow_case(case, actual_result)

    assert metrics["route_correct"] is True
    assert metrics["priority_correct"] is True
    assert metrics["stage_correct"] is True
    assert metrics["score_in_range"] is True
    assert metrics["crm_writeback_correct"] is True
    assert metrics["task_generation_correct"] is True
    assert metrics["required_task_hit_rate"] == 1.0


def test_evaluate_workflow_case_keeps_success_independent_from_accuracy():
    case = {
        "expected_workflow": {
            "lead_score_range": [0, 49],
            "lead_priority": "low",
            "opportunity_stage": "discovery",
            "expected_route": "low_priority_nurture",
            "should_write_crm": False,
            "should_generate_tasks": False,
            "required_task_titles": [],
            "required_risk_flags": [],
        }
    }
    actual_result = {
        "workflow_log": [{"route": "high_priority_follow_up"}],
        "lead_score": 96,
        "lead_priority": "high",
        "opportunity_stage": "proposal",
        "crm_update_ids": ["crm-1"],
        "task_payload": [{"title": "Prepare workshop agenda"}],
    }

    metrics = evaluate_workflow_case(case, actual_result)

    assert metrics["workflow_success"] is True
    assert metrics["route_correct"] is False
    assert metrics["score_in_range"] is False


def test_evaluate_workflow_case_allows_loose_required_task_title_matching():
    case = {
        "expected_workflow": {
            "lead_score_range": [50, 79],
            "lead_priority": "medium",
            "opportunity_stage": "qualification",
            "expected_route": "standard_follow_up",
            "should_write_crm": True,
            "should_generate_tasks": True,
            "required_task_titles": ["Prepare workshop"],
            "required_risk_flags": [],
        }
    }
    actual_result = {
        "workflow_log": [{"route": "standard_follow_up"}],
        "lead_score": 72,
        "lead_priority": "medium",
        "opportunity_stage": "qualification",
        "crm_update_ids": ["crm-1"],
        "task_payload": [{"title": "Prepare workshop agenda"}],
    }

    metrics = evaluate_workflow_case(case, actual_result)

    assert metrics["required_task_hit_rate"] == 1.0


def test_evaluate_workflow_case_uses_explicit_mcp_writeback_flag_and_nested_actions():
    case = {
        "expected_workflow": {
            "lead_score_range": [80, 95],
            "lead_priority": "high",
            "opportunity_stage": "proposal",
            "expected_route": "high_priority_follow_up",
            "should_write_crm": True,
            "should_generate_tasks": True,
            "required_task_titles": ["execute contract documents"],
            "required_risk_flags": [],
        }
    }
    actual_result = {
        "execution_mode": "mcp",
        "workflow_log": ["high_priority_follow_up", "write_back_crm"],
        "lead_score": 88,
        "lead_priority": "high",
        "opportunity_stage": "proposal",
        "crm_update_ids": [],
        "crm_writeback_performed": True,
        "task_payload": [],
        "follow_up_plan": {
            "follow_up_plan": {
                "next_actions": [
                    {"action": "Authorize City Manager to execute contract documents"}
                ]
            }
        },
    }

    metrics = evaluate_workflow_case(case, actual_result)

    assert metrics["crm_writeback_correct"] is True
    assert metrics["task_generation_correct"] is True
    assert metrics["required_task_hit_rate"] == 1.0


def test_evaluate_workflow_case_merges_task_payload_and_follow_up_actions():
    case = {
        "expected_workflow": {
            "lead_score_range": [50, 79],
            "lead_priority": "medium",
            "opportunity_stage": "qualification",
            "expected_route": "standard_follow_up",
            "should_write_crm": True,
            "should_generate_tasks": True,
            "required_task_titles": ["pricing review"],
            "required_risk_flags": [],
        }
    }
    actual_result = {
        "workflow_log": ["standard_follow_up", "write_back_crm"],
        "lead_score": 65,
        "lead_priority": "medium",
        "opportunity_stage": "qualification",
        "crm_writeback_performed": True,
        "task_payload": [{"title": "Clarify qualification gaps"}],
        "follow_up_plan": {
            "follow_up_plan": {
                "next_actions": [
                    {"action": "Prepare and send detailed pricing breakdown"}
                ]
            }
        },
    }

    metrics = evaluate_workflow_case(case, actual_result)

    assert metrics["task_generation_correct"] is True
    assert metrics["required_task_hit_rate"] == 1.0
