from pathlib import Path

from sales_copilot.graph import build_sales_copilot_graph, route_after_lead_evaluation


class _FakeLLMClient:
    def complete(self, messages, response_format=None):
        return "{}"


def test_route_after_lead_evaluation_returns_need_more_info():
    state = {
        "meeting_summary": {"confirmed_needs": []},
        "lead_score": 0,
        "lead_priority": "unknown",
        "risk_flags": ["missing_required_facts"],
    }

    route = route_after_lead_evaluation(state)

    assert route == "need_more_info"


def test_route_after_lead_evaluation_returns_need_more_info_for_empty_summary():
    state = {
        "meeting_summary": {},
        "lead_score": 90,
        "lead_priority": "high",
        "risk_flags": ["missing_budget"],
    }

    route = route_after_lead_evaluation(state)

    assert route == "need_more_info"


def test_route_after_lead_evaluation_returns_need_more_info_for_invalid_lead_score():
    state = {
        "meeting_summary": {"confirmed_needs": ["deployment options"]},
        "lead_score": None,
        "lead_priority": "high",
        "risk_flags": [],
    }

    route = route_after_lead_evaluation(state)

    assert route == "need_more_info"


def test_route_after_lead_evaluation_returns_low_priority_nurture():
    state = {
        "meeting_summary": {"confirmed_needs": ["pricing overview"]},
        "lead_score": 40,
        "lead_priority": "low",
        "risk_flags": [],
    }

    route = route_after_lead_evaluation(state)

    assert route == "low_priority_nurture"


def test_route_after_lead_evaluation_returns_standard_follow_up():
    state = {
        "meeting_summary": {"confirmed_needs": ["deployment options"]},
        "lead_score": 50,
        "lead_priority": "medium",
        "risk_flags": [],
    }

    route = route_after_lead_evaluation(state)

    assert route == "standard_follow_up"


def test_route_after_lead_evaluation_returns_high_priority_follow_up():
    state = {
        "meeting_summary": {"confirmed_needs": ["private deployment"]},
        "lead_score": 80,
        "lead_priority": "high",
        "risk_flags": [],
    }

    route = route_after_lead_evaluation(state)

    assert route == "high_priority_follow_up"


def test_route_after_lead_evaluation_requires_exact_missing_facts_flag():
    state = {
        "meeting_summary": {"confirmed_needs": ["private deployment"]},
        "lead_score": 90,
        "lead_priority": "high",
        "risk_flags": ["missing_required_facts", "missing_budget"],
    }

    route = route_after_lead_evaluation(state)

    assert route == "high_priority_follow_up"


def test_need_more_info_branch_skips_write_back_crm(tmp_path: Path):
    graph = build_sales_copilot_graph(
        llm_client=_FakeLLMClient(),
        database_path=tmp_path / "sales_copilot.db",
    )

    result = graph.invoke(
        {
            "meeting_summary": {"confirmed_needs": []},
            "lead_score": 10,
            "lead_priority": "unknown",
            "risk_flags": ["missing_required_facts"],
            "workflow_log": [],
        }
    )

    assert "need_more_info" in result["workflow_log"]
    assert "write_back_crm" not in result["workflow_log"]
    assert result["workflow_log"][-1] == "generate_dashboard_output"


def test_low_priority_branch_runs_through_write_back_crm(tmp_path: Path):
    graph = build_sales_copilot_graph(
        llm_client=_FakeLLMClient(),
        database_path=tmp_path / "sales_copilot.db",
    )

    result = graph.invoke(
        {
            "meeting_summary": {"confirmed_needs": ["pricing overview"]},
            "lead_score": 40,
            "lead_priority": "low",
            "risk_flags": [],
            "workflow_log": [],
        }
    )

    assert result["workflow_log"] == [
        "ingest_files",
        "parse_meeting_note",
        "retrieve_context",
        "load_account_memory",
        "evaluate_lead",
        "low_priority_nurture",
        "write_back_crm",
        "generate_dashboard_output",
    ]


def test_standard_follow_up_branch_runs_through_write_back_crm(tmp_path: Path):
    graph = build_sales_copilot_graph(
        llm_client=_FakeLLMClient(),
        database_path=tmp_path / "sales_copilot.db",
    )

    result = graph.invoke(
        {
            "meeting_summary": {"confirmed_needs": ["deployment options"]},
            "lead_score": 60,
            "lead_priority": "medium",
            "risk_flags": [],
            "workflow_log": [],
        }
    )

    assert result["workflow_log"] == [
        "ingest_files",
        "parse_meeting_note",
        "retrieve_context",
        "load_account_memory",
        "evaluate_lead",
        "standard_follow_up",
        "write_back_crm",
        "generate_dashboard_output",
    ]


def test_build_sales_copilot_graph_compiles_with_stubs(tmp_path: Path):
    graph = build_sales_copilot_graph(
        llm_client=_FakeLLMClient(),
        database_path=tmp_path / "sales_copilot.db",
    )

    assert hasattr(graph, "invoke")
