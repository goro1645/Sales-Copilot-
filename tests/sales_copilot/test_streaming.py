from sales_copilot.streaming import (
    make_content_delta_event,
    make_state_patch_event,
    stream_llm_completion,
)


class _FakeStreamingLLM:
    def stream(self, messages, tools=None):
        del messages, tools
        yield {"type": "content_delta", "text": "hel"}
        yield {"type": "content_delta", "text": "lo"}
        yield {"type": "message_finished", "finish_reason": "stop"}


class _FakeCompleteOnlyLLM:
    def complete(self, messages, response_format=None):
        del messages, response_format
        return "fallback"


def _drain_stream(generator):
    events = []
    try:
        while True:
            events.append(next(generator))
    except StopIteration as stop:
        return events, stop.value


def test_make_content_delta_event_includes_node_and_text():
    event = make_content_delta_event("parse_meeting_note", "hello")
    assert event == {
        "type": "content_delta",
        "node": "parse_meeting_note",
        "text": "hello",
    }


def test_make_state_patch_event_wraps_patch():
    event = make_state_patch_event("evaluate_lead", {"lead_priority": "high"})
    assert event["type"] == "state_patch"
    assert event["node"] == "evaluate_lead"
    assert event["patch"] == {"lead_priority": "high"}


def test_stream_llm_completion_forwards_stream_events_and_returns_joined_text():
    events, content = _drain_stream(
        stream_llm_completion(
            llm_client=_FakeStreamingLLM(),
            node="parse_meeting_note",
            messages=[{"role": "user", "content": "hi"}],
            response_format={"type": "json_object"},
        )
    )

    assert content == "hello"
    assert events == [
        {"type": "content_delta", "node": "parse_meeting_note", "text": "hel"},
        {"type": "content_delta", "node": "parse_meeting_note", "text": "lo"},
        {"type": "message_finished", "node": "parse_meeting_note", "finish_reason": "stop"},
    ]


def test_stream_llm_completion_falls_back_to_complete_when_stream_is_missing():
    events, content = _drain_stream(
        stream_llm_completion(
            llm_client=_FakeCompleteOnlyLLM(),
            node="evaluate_lead",
            messages=[{"role": "user", "content": "hi"}],
            response_format={"type": "json_object"},
        )
    )

    assert content == "fallback"
    assert events == [
        {"type": "content_delta", "node": "evaluate_lead", "text": "fallback"},
        {"type": "message_finished", "node": "evaluate_lead", "finish_reason": "stop"},
    ]
