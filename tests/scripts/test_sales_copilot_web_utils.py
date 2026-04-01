from scripts.sales_copilot_web_utils import (
    build_card_html,
    build_dashboard_cards,
    build_summary_html,
    clear_run_result_state,
    normalize_context_rows,
    normalize_task_rows,
    escape_html_text,
)


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


def test_escape_html_text_escapes_angle_brackets_and_quotes():
    assert escape_html_text('<script>"x"&"y"</script>') == "&lt;script&gt;&quot;x&quot;&amp;&quot;y&quot;&lt;/script&gt;"


def test_build_card_html_escapes_dynamic_values():
    html = build_card_html('<b>Label</b>', '<i>Value</i>', 'note & more')

    assert "&lt;b&gt;Label&lt;/b&gt;" in html
    assert "&lt;i&gt;Value&lt;/i&gt;" in html
    assert "note &amp; more" in html


def test_build_summary_html_escapes_dynamic_content():
    html = build_summary_html('<span>Summary</span>')

    assert "&lt;span&gt;Summary&lt;/span&gt;" in html


def test_normalize_context_rows_handles_mixed_matched_terms():
    rows = normalize_context_rows(
        {
            "retrieved_docs": [
                {
                    "source_name": "deployment-options",
                    "score": 9,
                    "matched_terms": [1, None, "foo"],
                    "chunk_text": "Deployment details",
                }
            ]
        }
    )

    assert rows == [
        {
            "Rank": 1,
            "Source": "deployment-options",
            "Score": 9,
            "Matched Terms": "1, foo",
            "Snippet": "Deployment details",
        }
    ]


def test_normalize_task_rows_handles_mixed_task_payloads():
    rows = normalize_task_rows(
        {
            "task_payload": [
                {
                    "title": "Send proposal",
                    "priority": "high",
                    "owner": None,
                    "due_at": 20260403,
                    "status": "open",
                },
                "ignore me",
            ]
        }
    )

    assert rows == [
        {
            "Rank": 1,
            "Title": "Send proposal",
            "Priority": "high",
            "Owner": "Sales",
            "Due": "20260403",
            "Status": "open",
        }
    ]


def test_normalize_task_rows_ignores_bad_follow_up_plan_shapes():
    rows = normalize_task_rows({"follow_up_plan": "oops"})

    assert rows == []


def test_clear_run_result_state_clears_previous_result_and_sets_error():
    session_state = {"last_result": {"lead_score": 88}, "last_error": ""}

    clear_run_result_state(session_state, "Missing API key")

    assert session_state["last_result"] is None
    assert session_state["last_error"] == "Missing API key"


def test_build_dashboard_cards_uses_zero_for_non_numeric_counts():
    cards = build_dashboard_cards({"retrieved_doc_count": "abc"})

    assert cards["Retrieved Docs"] == "0"
