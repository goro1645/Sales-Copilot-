from sales_copilot.stream_sse import encode_sse_event, iter_sse_events


def test_encode_sse_event_serializes_event_type_and_json_payload():
    payload = encode_sse_event({"type": "content_delta", "node": "parse_meeting_note", "text": "hi"})
    assert "event: content_delta" in payload
    assert '"text": "hi"' in payload


def test_iter_sse_events_finishes_cleanly_after_error_event_and_exception():
    def failing_events():
        yield {"type": "workflow_started", "workflow_name": "sales_copilot", "execution_mode": "direct"}
        yield {"type": "error", "node": "sales_copilot", "message": "LLM returned invalid JSON"}
        raise ValueError("LLM returned invalid JSON")

    frames = list(iter_sse_events(failing_events()))

    assert any("event: workflow_started" in frame for frame in frames)
    assert sum("event: error" in frame for frame in frames) == 1
