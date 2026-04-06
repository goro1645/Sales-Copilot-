import json
from pathlib import Path

from sales_copilot.storage import get_account_memory, list_accounts, list_crm_updates, list_meeting_records, list_tasks
from sales_copilot.runner import run_sales_copilot
from sales_copilot.tools import get_open_tasks


class FakeLLM:
    def __init__(self) -> None:
        self.calls: list[list[dict]] = []

    def complete(self, messages, response_format=None):
        self.calls.append(messages)
        prompt_text = "\n".join(message["content"] for message in messages)
        if "Parse the meeting notes" in prompt_text:
            return (
                '{"account_name": "Acme Robotics", "customer_roles": ["CTO"], '
                '"confirmed_needs": ["private deployment"], "objections": [], '
                '"next_steps": ["send proposal"], "budget_signals": ["budget approved"], '
                '"timeline_signals": ["this quarter"], "competitors": []}'
            )
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
        raise AssertionError(f"Unexpected prompt: {prompt_text}")


class RefreshingLLM:
    def __init__(self) -> None:
        self.calls: list[list[dict]] = []
        self.run_index = 0

    def complete(self, messages, response_format=None):
        self.calls.append(messages)
        prompt_text = "\n".join(message["content"] for message in messages)
        if "Parse the meeting notes" in prompt_text:
            self.run_index += 1
            if self.run_index == 1:
                return (
                    '{"account_name": "Acme Robotics", "customer_roles": ["CTO"], '
                    '"confirmed_needs": ["private deployment"], "objections": [], '
                    '"next_steps": ["send proposal"], "budget_signals": ["budget approved"], '
                    '"timeline_signals": ["this quarter"], "competitors": []}'
                )
            return (
                '{"account_name": "Acme Robotics", "customer_roles": ["CFO"], '
                '"confirmed_needs": ["pricing and procurement"], "objections": [], '
                '"next_steps": ["review pricing"], "budget_signals": ["budget approved"], '
                '"timeline_signals": ["next quarter"], "competitors": []}'
            )
        if "Evaluate the lead" in prompt_text:
            if self.run_index == 1:
                return (
                    '{"lead_score": 88, "lead_priority": "high", "opportunity_stage": "proposal", '
                    '"risk_flags": [], "reasons": ["strong fit"], "evidence": ["confirmed need"]}'
                )
            return (
                '{"lead_score": 70, "lead_priority": "medium", "opportunity_stage": "proposal", '
                '"risk_flags": [], "reasons": ["still strong"], "evidence": ["confirmed need"]}'
            )
        if "follow-up plan" in prompt_text.lower():
            if self.run_index == 1:
                return (
                    '{"summary": "Send proposal", "tasks": [{"title": "Send proposal", '
                    '"description": "Send first proposal", "priority": "high", '
                    '"due_at": "2026-04-03"}]}'
                )
            return (
                '{"summary": "Send updated proposal", "tasks": [{"title": "Send proposal", '
                '"description": "Send revised proposal", "priority": "medium", '
                '"due_at": "2026-04-03"}]}'
            )
        raise AssertionError(f"Unexpected prompt: {prompt_text}")


def test_run_sales_copilot_returns_dashboard_and_crm_ids(tmp_path: Path):
    result = run_sales_copilot(
        customer_profile_text="Acme Robotics is a manufacturing company.",
        meeting_note_text="CTO requested a proposal for private deployment.",
        database_path=tmp_path / "sales.db",
        llm_client=FakeLLM(),
    )

    assert result["lead_score"] == 88
    assert result["dashboard_output"]["account_name"] == "Acme Robotics"
    assert result["crm_update_ids"]


def test_run_sales_copilot_turns_missing_facts_into_follow_up_tasks_and_crm_write_back(tmp_path: Path):
    class MissingFactsLLM(FakeLLM):
        def complete(self, messages, response_format=None):
            self.calls.append(messages)
            prompt_text = "\n".join(message["content"] for message in messages)
            if "Parse the meeting notes" in prompt_text:
                return (
                    '{"account_name": "Northwind Traders", "customer_roles": [], '
                    '"confirmed_needs": [], "objections": [], "next_steps": [], '
                    '"budget_signals": [], "timeline_signals": [], "competitors": []}'
                )
            if "Evaluate the lead" in prompt_text:
                return (
                    '{"lead_score": 12, "lead_priority": "low", "opportunity_stage": "discovery", '
                    '"risk_flags": ["missing_required_facts"], "reasons": ["missing details"], '
                    '"evidence": []}'
                )
            raise AssertionError(f"Unexpected prompt: {prompt_text}")

    result = run_sales_copilot(
        customer_profile_text="Northwind Traders is a retail company.",
        meeting_note_text="Need follow-up.",
        database_path=tmp_path / "sales.db",
        llm_client=MissingFactsLLM(),
    )

    assert result["follow_up_plan"]["summary"]
    assert result["crm_update_ids"]
    assert result["task_payload"]
    assert any(task["title"] == "Confirm budget range" for task in result["task_payload"])


def test_run_sales_copilot_uses_meeting_account_name_when_profile_is_generic(tmp_path: Path):
    class MeetingNameLLM(FakeLLM):
        def complete(self, messages, response_format=None):
            self.calls.append(messages)
            prompt_text = "\n".join(message["content"] for message in messages)
            if "Parse the meeting notes" in prompt_text:
                return (
                    '{"account_name": "Acme Robotics", "customer_roles": ["CTO"], '
                    '"confirmed_needs": ["private deployment"], "objections": [], '
                    '"next_steps": ["send proposal"], "budget_signals": ["budget approved"], '
                    '"timeline_signals": ["this quarter"], "competitors": []}'
                )
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
            raise AssertionError(f"Unexpected prompt: {prompt_text}")

    result = run_sales_copilot(
        customer_profile_text="Enterprise customer profile.",
        meeting_note_text="CTO requested a proposal for private deployment.",
        database_path=tmp_path / "sales.db",
        llm_client=MeetingNameLLM(),
    )

    accounts = list_accounts(tmp_path / "sales.db")

    assert result["dashboard_output"]["account_name"] == "Acme Robotics"
    assert accounts[0]["name"] == "Acme Robotics"


def test_run_sales_copilot_repeated_input_does_not_duplicate_persisted_rows(tmp_path: Path):
    db_path = tmp_path / "sales.db"

    first = run_sales_copilot(
        customer_profile_text="Acme Robotics is a manufacturing company.",
        meeting_note_text="CTO requested a proposal for private deployment.",
        database_path=db_path,
        llm_client=FakeLLM(),
    )
    second = run_sales_copilot(
        customer_profile_text="Acme Robotics is a manufacturing company.",
        meeting_note_text="CTO requested a proposal for private deployment.",
        database_path=db_path,
        llm_client=FakeLLM(),
    )

    assert first["dashboard_output"]["account_name"] == second["dashboard_output"]["account_name"]
    assert len(list_accounts(db_path)) == 1
    assert len(list_meeting_records(db_path)) == 1
    assert len(list_tasks(db_path)) == 1
    assert len(list_crm_updates(db_path)) == 1


def test_run_sales_copilot_reuses_prior_history_and_open_tasks_for_repeated_account(tmp_path: Path):
    db_path = tmp_path / "sales.db"

    class RepeatedAccountLLM:
        def __init__(self) -> None:
            self.calls: list[list[dict]] = []

        def complete(self, messages, response_format=None):
            self.calls.append(messages)
            prompt_text = "\n".join(message["content"] for message in messages)
            if "Parse the meeting notes" in prompt_text:
                if "CTO requested a proposal for private deployment." in prompt_text:
                    return (
                        '{"account_name": "Acme Robotics", "customer_roles": ["CTO"], '
                        '"confirmed_needs": ["private deployment"], "objections": [], '
                        '"next_steps": ["send proposal"], "budget_signals": ["budget approved"], '
                        '"timeline_signals": ["this quarter"], "competitors": []}'
                    )
                return (
                    '{"account_name": "Acme Robotics", "customer_roles": ["CFO"], '
                    '"confirmed_needs": ["pricing and procurement"], "objections": [], '
                    '"next_steps": ["review pricing"], "budget_signals": ["budget approved"], '
                    '"timeline_signals": ["next quarter"], "competitors": []}'
                )
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
            raise AssertionError(f"Unexpected prompt: {prompt_text}")

    llm = RepeatedAccountLLM()

    first = run_sales_copilot(
        customer_profile_text="Acme Robotics is a manufacturing company.",
        meeting_note_text="CTO requested a proposal for private deployment.",
        database_path=db_path,
        llm_client=llm,
    )
    second = run_sales_copilot(
        customer_profile_text="Acme Robotics is a manufacturing company.",
        meeting_note_text="CFO asked about deployment pricing and procurement timing.",
        database_path=db_path,
        llm_client=llm,
        account_id=first["account_id"],
    )

    assert first["account_id"] == second["account_id"]
    assert second["open_tasks"]
    assert any(row["meeting_note_raw"] == "CTO requested a proposal for private deployment." for row in second["retrieved_docs"])
    assert any(task["title"] == "Send proposal" for task in second["open_tasks"])
    memory_row = get_account_memory(db_path, first["account_id"])
    assert "private deployment" in memory_row["confirmed_needs_json"]
    assert "pricing and procurement" in memory_row["confirmed_needs_json"]
    assert len(list_tasks(db_path)) == 2


def test_run_sales_copilot_keeps_same_task_title_for_different_meetings(tmp_path: Path):
    db_path = tmp_path / "sales.db"

    class RepeatedAccountLLM:
        def __init__(self) -> None:
            self.calls: list[list[dict]] = []

        def complete(self, messages, response_format=None):
            self.calls.append(messages)
            prompt_text = "\n".join(message["content"] for message in messages)
            if "Parse the meeting notes" in prompt_text:
                if "CTO requested a proposal for private deployment." in prompt_text:
                    return (
                        '{"account_name": "Acme Robotics", "customer_roles": ["CTO"], '
                        '"confirmed_needs": ["private deployment"], "objections": [], '
                        '"next_steps": ["send proposal"], "budget_signals": ["budget approved"], '
                        '"timeline_signals": ["this quarter"], "competitors": []}'
                    )
                return (
                    '{"account_name": "Acme Robotics", "customer_roles": ["CFO"], '
                    '"confirmed_needs": ["pricing and procurement"], "objections": [], '
                    '"next_steps": ["review pricing"], "budget_signals": ["budget approved"], '
                    '"timeline_signals": ["next quarter"], "competitors": []}'
                )
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
            raise AssertionError(f"Unexpected prompt: {prompt_text}")

    llm = RepeatedAccountLLM()

    first = run_sales_copilot(
        customer_profile_text="Acme Robotics is a manufacturing company.",
        meeting_note_text="CTO requested a proposal for private deployment.",
        database_path=db_path,
        llm_client=llm,
    )
    second = run_sales_copilot(
        customer_profile_text="Acme Robotics is a manufacturing company.",
        meeting_note_text="CFO asked about deployment pricing and procurement timing.",
        database_path=db_path,
        llm_client=llm,
        account_id=first["account_id"],
    )

    assert first["account_id"] == second["account_id"]
    assert len(list_tasks(db_path)) == 2
    assert len(get_open_tasks(db_path, first["account_id"])) == 2
    assert second["open_tasks"]
    assert any(task["title"] == "Send proposal" for task in second["open_tasks"])
    assert any("CTO requested a proposal for private deployment." == row["meeting_note_raw"] for row in second["retrieved_docs"])


def test_run_sales_copilot_refreshes_existing_meeting_and_task_records(tmp_path: Path):
    db_path = tmp_path / "sales.db"
    llm = RefreshingLLM()

    first = run_sales_copilot(
        customer_profile_text="Acme Robotics is a manufacturing company.",
        meeting_note_text="CTO requested a proposal for private deployment.",
        database_path=db_path,
        llm_client=llm,
    )
    second = run_sales_copilot(
        customer_profile_text="Acme Robotics is a manufacturing company.",
        meeting_note_text="CTO requested a proposal for private deployment.",
        database_path=db_path,
        llm_client=llm,
        account_id=first["account_id"],
    )

    meeting_rows = list_meeting_records(db_path)
    task_rows = list_tasks(db_path)

    assert first["account_id"] == second["account_id"]
    assert len(meeting_rows) == 1
    assert json.loads(meeting_rows[0]["meeting_summary_json"])["confirmed_needs"] == ["pricing and procurement"]
    assert meeting_rows[0]["lead_score"] == 70
    assert meeting_rows[0]["priority"] == "medium"
    assert len(task_rows) == 1
    assert task_rows[0]["description"] == "Send revised proposal"
    assert task_rows[0]["priority"] == "medium"
    assert task_rows[0]["status"] == "open"


def test_run_sales_copilot_accepts_common_scoring_alias_fields(tmp_path: Path):
    class AliasScoringLLM(FakeLLM):
        def complete(self, messages, response_format=None):
            self.calls.append(messages)
            prompt_text = "\n".join(message["content"] for message in messages)
            if "Parse the meeting notes" in prompt_text:
                return (
                    '{"account_name": "BluePeak Health", "customer_roles": ["CIO", "Compliance Manager"], '
                    '"confirmed_needs": ["private deployment", "audit logging"], "objections": [], '
                    '"next_steps": ["schedule workshop"], "budget_signals": ["pilot budget approved"], '
                    '"timeline_signals": ["within 6 weeks"], "competitors": ["workflow automation vendor"]}'
                )
            if "Evaluate the lead" in prompt_text:
                return (
                    '{"score": 84, "priority": "high", "stage": "proposal", '
                    '"risks": ["security review"], "reasons": ["budget and timeline confirmed"], '
                    '"evidence": ["pilot budget approved", "within 6 weeks"]}'
                )
            if "follow-up plan" in prompt_text.lower():
                return (
                    '{"summary": "Prepare a compliance-focused workshop", "tasks": [{"title": "Prepare workshop", '
                    '"description": "Draft the workshop agenda", "priority": "high", '
                    '"due_at": "2026-04-04"}]}'
                )
            raise AssertionError(f"Unexpected prompt: {prompt_text}")

    result = run_sales_copilot(
        customer_profile_text="BluePeak Health is a healthcare group evaluating a sales copilot.",
        meeting_note_text="CIO asked for private deployment, audit logging, and a workshop within 6 weeks.",
        database_path=tmp_path / "sales.db",
        llm_client=AliasScoringLLM(),
    )

    assert result["lead_score"] == 84
    assert result["lead_priority"] == "high"
    assert result["opportunity_stage"] == "proposal"
    assert result["risk_flags"] == ["security review"]


def test_run_sales_copilot_accepts_nested_scoring_payloads_and_string_scores(tmp_path: Path):
    class NestedScoringLLM(FakeLLM):
        def complete(self, messages, response_format=None):
            self.calls.append(messages)
            prompt_text = "\n".join(message["content"] for message in messages)
            if "Parse the meeting notes" in prompt_text:
                return (
                    '{"account_name": "BluePeak Health", "customer_roles": ["CIO"], '
                    '"confirmed_needs": ["private deployment", "crm integration"], "objections": [], '
                    '"next_steps": ["prepare workshop"], "budget_signals": ["pilot budget approved"], '
                    '"timeline_signals": ["within 6 weeks"], "competitors": []}'
                )
            if "Evaluate the lead" in prompt_text:
                return (
                    '{"result": {"score": "84/100", "priority": "high", "stage": "proposal", '
                    '"risks": ["security review"], "reasons": ["budget confirmed"], '
                    '"evidence": ["pilot budget approved"]}}'
                )
            if "follow-up plan" in prompt_text.lower():
                return (
                    '{"summary": "Prepare the proposal workshop", "tasks": [{"title": "Prepare workshop", '
                    '"description": "Align workshop materials", "priority": "high", '
                    '"due_at": "2026-04-04"}]}'
                )
            raise AssertionError(f"Unexpected prompt: {prompt_text}")

    result = run_sales_copilot(
        customer_profile_text="BluePeak Health is evaluating a private deployment.",
        meeting_note_text="The CIO asked for a proposal workshop and confirmed the pilot budget.",
        database_path=tmp_path / "sales.db",
        llm_client=NestedScoringLLM(),
    )

    assert result["lead_score"] == 84
    assert result["lead_priority"] == "high"
    assert result["opportunity_stage"] == "proposal"
    assert result["risk_flags"] == ["security review"]
