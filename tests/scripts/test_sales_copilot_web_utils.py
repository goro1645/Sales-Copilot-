from scripts.sales_copilot_web_utils import (
    apply_stream_event_to_progress_state,
    append_stream_log_line,
    build_progress_panel_html,
    build_stream_api_payload,
    build_card_html,
    build_dashboard_cards,
    build_summary_html,
    clear_run_result_state,
    default_stream_progress_state,
    normalize_context_rows,
    normalize_task_rows,
    parse_sse_event_block,
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


def test_build_stream_api_payload_keeps_runtime_fields():
    payload = build_stream_api_payload(
        customer_profile_text="Acme",
        meeting_note_text="Need proposal",
        database_path="tmp.db",
        execution_mode="direct",
        api_key="key",
        api_base_url="https://api.deepseek.com",
        api_model="deepseek-chat",
    )

    assert payload["execution_mode"] == "direct"
    assert payload["api_model"] == "deepseek-chat"


def test_parse_sse_event_block_returns_event_dict():
    event = parse_sse_event_block(
        'event: workflow_started\ndata: {"type":"workflow_started","workflow_name":"sales_copilot"}'
    )

    assert event["type"] == "workflow_started"


def test_append_stream_log_line_accumulates_readable_log():
    text = append_stream_log_line(
        "",
        {"type": "node_started", "node": "parse_meeting_note", "streaming": True},
    )

    assert "parse_meeting_note" in text


def test_stream_helpers_can_extract_final_result_event():
    event = parse_sse_event_block(
        'event: workflow_finished\n'
        'data: {"type":"workflow_finished","result":{"dashboard_output":{"account_name":"Acme"}}}'
    )

    assert event["result"]["dashboard_output"]["account_name"] == "Acme"


def test_progress_state_tracks_running_stage_and_completion():
    state = default_stream_progress_state()
    state = apply_stream_event_to_progress_state(
        state,
        {"type": "workflow_started", "workflow_name": "sales_copilot", "execution_mode": "direct"},
    )
    state = apply_stream_event_to_progress_state(
        state,
        {"type": "node_started", "node": "parse_meeting_note", "streaming": True},
    )
    state = apply_stream_event_to_progress_state(
        state,
        {"type": "node_finished", "node": "parse_meeting_note"},
    )

    assert state["status"] == "running"
    assert state["current_stage"] == "parse"
    assert "parse" in state["completed_stages"]


def test_progress_state_surfaces_errors_and_html_summary():
    state = default_stream_progress_state()
    state = apply_stream_event_to_progress_state(
        state,
        {"type": "error", "node": "sales_copilot", "message": "LLM returned invalid JSON"},
    )

    html = build_progress_panel_html(state)

    assert state["status"] == "failed"
    assert "LLM returned invalid JSON" in state["error_message"]
    assert "Run failed" in html
