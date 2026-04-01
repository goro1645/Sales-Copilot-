import inspect

from sales_copilot.prompts import (
    build_crm_update_messages,
    build_dashboard_summary_messages,
    build_followup_plan_messages,
    build_lead_scoring_messages,
    build_meeting_parse_messages,
)


def test_build_meeting_parse_messages_requests_json_and_uses_notes():
    messages = build_meeting_parse_messages(
        customer_profile_text="Enterprise buyer profile with security requirements.",
        meeting_note_text="Discussed pricing, timeline, and security review.",
    )

    assert messages[0]["role"] == "system"
    assert "json" in messages[0]["content"].lower()
    assert "background" in messages[0]["content"].lower()
    assert "disambiguation" in messages[0]["content"].lower()
    assert "account_name" in messages[1]["content"]
    assert "customer_roles" in messages[1]["content"]
    assert "confirmed_needs" in messages[1]["content"]
    assert "objections" in messages[1]["content"]
    assert "next_steps" in messages[1]["content"]
    assert "budget_signals" in messages[1]["content"]
    assert "timeline_signals" in messages[1]["content"]
    assert "competitors" in messages[1]["content"]
    assert "enterprise buyer profile" in messages[1]["content"].lower()
    assert "pricing" in messages[1]["content"]


def test_build_lead_scoring_messages_mentions_json_and_input_context():
    assert str(inspect.signature(build_lead_scoring_messages)) == (
        "(*, customer_profile_text: str, meeting_summary: dict, retrieved_docs: list[dict], "
        "account_memory: dict) -> list[dict[str, str]]"
    )

    messages = build_lead_scoring_messages(
        customer_profile_text="Enterprise account with budget approved.",
        meeting_summary={"summary": "They want a pilot next month."},
        retrieved_docs=[{"type": "doc", "content": "integration"}, {"type": "note", "content": "demo"}],
        account_memory={"prior_call": "Strong technical fit."},
    )

    assert messages[0]["role"] == "system"
    assert "json" in messages[0]["content"].lower()
    assert "budget approved" in messages[1]["content"]
    assert "retrieved context" in messages[1]["content"].lower()
    assert "account memory" in messages[1]["content"].lower()
    assert '"summary": "They want a pilot next month."' in messages[1]["content"]
    assert '"type": "doc"' in messages[1]["content"]
    assert '"prior_call": "Strong technical fit."' in messages[1]["content"]


def test_build_followup_plan_messages_mentions_no_hallucination():
    assert str(inspect.signature(build_followup_plan_messages)) == (
        "(*, meeting_summary: dict, opportunity_stage: str, risk_flags: list[str]) -> list[dict[str, str]]"
    )

    messages = build_followup_plan_messages(
        meeting_summary={"summary": "Interested in a pilot."},
        opportunity_stage="Proposal",
        risk_flags=["pricing risk", "no champion"],
    )

    assert messages[0]["role"] == "system"
    assert "do not hallucinate" in messages[0]["content"].lower()
    assert "proposal" in messages[1]["content"].lower()
    assert "pricing risk" in messages[1]["content"].lower()
    assert '"summary": "Interested in a pilot."' in messages[1]["content"]


def test_build_crm_update_messages_carries_current_crm_state():
    messages = build_crm_update_messages(
        lead_context="Decision maker asked for an updated quote.",
        meeting_parse_json='{"crm_updates":["update close date"]}',
        current_crm_state_json='{"owner":"alice"}',
    )

    assert messages[0]["role"] == "system"
    assert "crm" in messages[0]["content"].lower()
    assert "alice" in messages[1]["content"]


def test_build_dashboard_summary_messages_mentions_output_structure():
    messages = build_dashboard_summary_messages(
        meeting_parse_json='{"company":"MiniMind"}',
        lead_scoring_json='{"score":87}',
        followup_plan_json='{"next_action":"send contract"}',
        crm_update_json='{"status":"updated"}',
    )

    assert messages[0]["role"] == "system"
    assert "dashboard" in messages[0]["content"].lower()
    assert "json" in messages[0]["content"].lower()
    assert "MiniMind" in messages[1]["content"]
