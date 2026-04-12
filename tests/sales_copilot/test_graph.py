from pathlib import Path

from sales_copilot.graph import build_sales_copilot_graph, route_after_lead_evaluation
from sales_copilot.storage import save_account


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
        if "follow-up plan" in prompt_text.lower():
            return (
                '{"summary": "Send proposal", "tasks": [{"title": "Send proposal", '
                '"description": "Send tailored proposal", "priority": "high", '
                '"due_at": "2026-04-03"}]}'
            )
        return "{}"


class _DashboardNameLLMClient:
    def complete(self, messages, response_format=None):
        prompt_text = "\n".join(message["content"] for message in messages)
        if "Evaluate the lead" in prompt_text:
            return (
                '{"lead_score": 88, "lead_priority": "high", "opportunity_stage": "proposal", '
                '"risk_flags": [], "reasons": ["strong fit"], "evidence": ["confirmed need"]}'
            )
        if "follow-up plan" in prompt_text.lower():
            return (
                '{"summary": "Send proposal", "tasks": [{"title": "Send proposal", '
                '"description": "Send tailored proposal", "priority": "high", '
                '"due_at": "2026-04-03"}]}'
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
        "build_task_candidates",
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
        "build_task_candidates",
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


def test_standard_follow_up_flow_records_build_task_candidates(tmp_path: Path) -> None:
    graph = build_sales_copilot_graph(
        llm_client=_FakeLLMClient(),
        database_path=tmp_path / "sales_copilot.db",
    )

    result = graph.invoke(
        {
            "meeting_summary": {
                "confirmed_needs": ["proposal support"],
                "next_steps": ["send tailored proposal by Friday"],
            },
            "lead_score": 60,
            "lead_priority": "medium",
            "opportunity_stage": "proposal",
            "risk_flags": [],
            "workflow_log": [],
        }
    )

    assert "build_task_candidates" in result["workflow_log"]
    assert result["task_candidates"][0]["text"] == "send tailored proposal by Friday"


def test_standard_follow_up_merges_candidate_tasks_when_model_returns_empty_tasks(tmp_path: Path) -> None:
    class _SparseLLM(_FakeLLMClient):
        def complete(self, messages, response_format=None):
            prompt_text = "\n".join(message["content"] for message in messages)
            if "follow-up plan" in prompt_text.lower():
                return '{"summary": "Execute the agreed follow-up.", "tasks": []}'
            return super().complete(messages, response_format=response_format)

    graph = build_sales_copilot_graph(
        llm_client=_SparseLLM(),
        database_path=tmp_path / "sales_copilot.db",
    )

    result = graph.invoke(
        {
            "meeting_summary": {
                "confirmed_needs": ["proposal support"],
                "next_steps": ["send tailored proposal by Friday"],
            },
            "lead_score": 82,
            "lead_priority": "high",
            "opportunity_stage": "proposal",
            "risk_flags": [],
            "workflow_log": [],
        }
    )

    assert any(task["title"] == "Send tailored proposal" for task in result["task_payload"])


def test_retrieve_context_node_uses_hybrid_retrieval_metadata(tmp_path: Path, monkeypatch):
    from sales_copilot.graph import retrieve_context_node
    from sales_copilot.storage import init_storage

    db_path = tmp_path / "sales.db"
    init_storage(db_path)

    monkeypatch.setattr(
        "sales_copilot.graph.hybrid_retrieve_knowledge_chunks",
        lambda *args, **kwargs: [
            {
                "id": 1,
                "source_name": "Doc A",
                "chunk_text": "Private deployment",
                "retrieval_mode": "hybrid",
                "vector_score": 0.95,
                "keyword_score": 1.0,
                "hybrid_score": 0.965,
            }
        ],
    )

    result = retrieve_context_node(
        {
            "meeting_summary": {"confirmed_needs": ["private deployment"]},
            "meeting_note_raw": "Need private deployment.",
        },
        database_path=db_path,
    )

    assert result["retrieved_docs"][0]["retrieval_mode"] == "hybrid"
    assert result["workflow_log"][-1] == "retrieve_context"


def test_retrieve_context_node_supports_explicit_keyword_only_mode(tmp_path: Path):
    from sales_copilot.graph import retrieve_context_node
    from sales_copilot.tools import sample_product_chunks, seed_knowledge_chunks

    db_path = tmp_path / "sales.db"
    seed_knowledge_chunks(db_path, sample_product_chunks())

    result = retrieve_context_node(
        {
            "meeting_summary": {"confirmed_needs": ["private deployment"]},
            "meeting_note_raw": "Need private deployment.",
        },
        database_path=db_path,
        retrieval_embedder=None,
    )

    assert result["retrieved_docs"]
    assert all(doc["retrieval_mode"] == "keyword_only" for doc in result["retrieved_docs"])


def test_dashboard_output_prefers_database_account_name(tmp_path: Path):
    db_path = tmp_path / "sales_copilot.db"
    account_id = save_account(
        db_path,
        {
            "name": "Acme Robotics",
            "industry": "Manufacturing",
            "size_segment": "Mid-Market",
            "status": "active",
            "opportunity_stage": "discovery",
        },
    )
    graph = build_sales_copilot_graph(
        llm_client=_DashboardNameLLMClient(),
        database_path=db_path,
    )

    result = graph.invoke(
        {
            "account_id": account_id,
            "customer_profile_raw": "Enterprise customer profile.",
            "meeting_summary": {"confirmed_needs": ["private deployment"]},
            "meeting_summary_provided": True,
            "lead_score": 88,
            "lead_priority": "high",
            "risk_flags": [],
            "workflow_log": [],
        }
    )

    assert result["dashboard_output"]["account_name"] == "Acme Robotics"


def test_build_sales_copilot_graph_compiles_with_stubs(tmp_path: Path):
    graph = build_sales_copilot_graph(
        llm_client=_FakeLLMClient(),
        database_path=tmp_path / "sales_copilot.db",
    )

    assert hasattr(graph, "invoke")
