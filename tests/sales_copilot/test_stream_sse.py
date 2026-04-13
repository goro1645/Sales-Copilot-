from sales_copilot.stream_sse import encode_sse_event


def test_encode_sse_event_serializes_event_type_and_json_payload():
    payload = encode_sse_event({"type": "content_delta", "node": "parse_meeting_note", "text": "hi"})
    assert "event: content_delta" in payload
    assert '"text": "hi"' in payload
