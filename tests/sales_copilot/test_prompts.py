from sales_copilot.prompts import (
    build_crm_update_messages,
    build_dashboard_summary_messages,
    build_followup_plan_messages,
    build_lead_scoring_messages,
    build_meeting_parse_messages,
)


def test_build_meeting_parse_messages_requests_json_and_uses_notes():
    messages = build_meeting_parse_messages(
        meeting_notes="Discussed pricing, timeline, and security review.",
    )

    assert messages[0]["role"] == "system"
    assert "json" in messages[0]["content"].lower()
    assert "do not invent" in messages[0]["content"].lower()
    assert "pricing" in messages[1]["content"]


def test_build_lead_scoring_messages_mentions_json_and_input_context():
    messages = build_lead_scoring_messages(
        lead_context="Enterprise account with budget approved.",
        meeting_parse_json='{"pain_points":["integration"],"next_steps":["demo"]}',
    )

    assert messages[0]["role"] == "system"
    assert "json" in messages[0]["content"].lower()
    assert "budget approved" in messages[1]["content"]
    assert "integration" in messages[1]["content"]


def test_build_followup_plan_messages_mentions_no_hallucination():
    messages = build_followup_plan_messages(
        lead_context="Interested in a pilot.",
        meeting_parse_json='{"next_steps":["send proposal"]}',
    )

    assert messages[0]["role"] == "system"
    assert "do not hallucinate" in messages[0]["content"].lower()
    assert "send proposal" in messages[1]["content"]


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
