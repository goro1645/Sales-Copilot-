from scripts.sales_copilot_web_utils import build_dashboard_cards


def test_build_dashboard_cards_formats_lead_summary():
    result = {
        "lead_score": 88,
        "lead_priority": "high",
        "opportunity_stage": "proposal",
        "risk_flags": ["budget_risk"],
    }

    cards = build_dashboard_cards(result)

    assert cards["Lead Score"] == "88"
    assert cards["Priority"] == "high"
    assert cards["Stage"] == "proposal"
    assert cards["Risk Flags"] == "budget_risk"


def test_build_dashboard_cards_uses_safe_defaults_for_missing_values():
    cards = build_dashboard_cards({})

    assert cards["Lead Score"] == "N/A"
    assert cards["Priority"] == "N/A"
    assert cards["Stage"] == "N/A"
    assert cards["Risk Flags"] == "None"
