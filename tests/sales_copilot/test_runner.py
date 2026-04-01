from pathlib import Path

from sales_copilot.runner import run_sales_copilot


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


def test_run_sales_copilot_handles_missing_facts_without_crm_write_back(tmp_path: Path):
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
    assert result["crm_update_ids"] == []
