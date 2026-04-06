from pathlib import Path

from sales_copilot.graph import build_sales_copilot_graph, route_after_lead_evaluation


class _FakeLLMClient:
    def complete(self, messages, response_format=None):
        return "{}"


class _RecordingLLMClient:
    def __init__(self) -> None:
        self.calls: list[list[dict]] = []

    def complete(self, messages, response_format=None):
        self.calls.append(messages)
        prompt_text = "\n".join(message["content"] for message in messages)
        if "Parse the meeting notes" in prompt_text:
            return (
                '{"account_name": "Acme Robotics", "customer_roles": ["CTO"], '
                '"confirmed_needs": ["pricing overview"], "objections": [], '
                '"next_steps": ["send proposal"], "budget_signals": ["budget approved"], '
                '"timeline_signals": ["this quarter"], "competitors": []}'
            )
        if "Evaluate the lead" in prompt_text:
            return (
                '{"lead_score": 40, "lead_priority": "low", "opportunity_stage": "discovery", '
                '"risk_flags": [], "reasons": ["needs nurture"], "evidence": ["pricing overview"]}'
            )
        return "{}"


def test_route_after_lead_evaluation_returns_need_more_info():
    state = {
        "meeting_summary": {},
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


def test_route_after_lead_evaluation_allows_high_score_with_missing_facts_to_progress():
    state = {
        "meeting_summary": {"confirmed_needs": ["private deployment"]},
        "lead_score": 75,
        "lead_priority": "high",
        "risk_flags": ["missing_required_facts"],
    }

    route = route_after_lead_evaluation(state)

    assert route == "standard_follow_up"


def test_need_more_info_branch_runs_through_write_back_crm_and_creates_tasks(tmp_path: Path):
    graph = build_sales_copilot_graph(
        llm_client=_FakeLLMClient(),
        database_path=tmp_path / "sales_copilot.db",
    )

    result = graph.invoke(
        {
            "meeting_summary": {},
            "lead_score": 10,
            "lead_priority": "unknown",
            "risk_flags": ["missing_required_facts"],
            "workflow_log": [],
        }
    )

    assert "need_more_info" in result["workflow_log"]
    assert "write_back_crm" in result["workflow_log"]
    assert result["workflow_log"][-1] == "generate_dashboard_output"
    assert result["crm_update_ids"]
    assert result["task_payload"]


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


def test_parse_meeting_note_uses_existing_summary_only_when_note_is_empty(tmp_path: Path):
    llm_client = _RecordingLLMClient()
    graph = build_sales_copilot_graph(
        llm_client=llm_client,
        database_path=tmp_path / "sales_copilot.db",
    )

    graph.invoke(
        {
            "customer_profile_raw": "Acme Robotics is a manufacturing company.",
            "meeting_note_raw": "Need pricing overview.",
            "meeting_summary": {"confirmed_needs": ["stale summary"]},
            "lead_score": 40,
            "lead_priority": "low",
            "risk_flags": [],
            "workflow_log": [],
        }
    )

    assert len(llm_client.calls) == 2
    assert "Parse the meeting notes" in "\n".join(message["content"] for message in llm_client.calls[0])
    assert "Evaluate the lead" in "\n".join(message["content"] for message in llm_client.calls[1])


def test_build_sales_copilot_graph_compiles_with_stubs(tmp_path: Path):
    graph = build_sales_copilot_graph(
        llm_client=_FakeLLMClient(),
        database_path=tmp_path / "sales_copilot.db",
    )

    assert hasattr(graph, "invoke")
