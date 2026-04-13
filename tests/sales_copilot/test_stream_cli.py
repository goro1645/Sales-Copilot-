from sales_copilot.stream_cli import render_stream_event


def test_render_stream_event_formats_node_started():
    line = render_stream_event({"type": "node_started", "node": "evaluate_lead", "streaming": True})
    assert "evaluate_lead" in line
    assert "started" in line.lower()


def test_render_stream_event_formats_tool_call_finished():
    line = render_stream_event(
        {
            "type": "tool_call_finished",
            "node": "evaluate_lead",
            "name": "classify_signal_candidates",
            "arguments": '{"classifications": []}',
        }
    )
    assert "classify_signal_candidates" in line
