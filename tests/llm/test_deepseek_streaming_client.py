import json

import pytest

from llm.deepseek_client import DeepSeekClient


def test_deepseek_client_stream_yields_content_and_finish_events(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def iter_lines(self, decode_unicode=True):
            yield 'data: {"choices":[{"delta":{"content":"Hello"}}]}'
            yield 'data: {"choices":[{"delta":{"content":" world"}}]}'
            yield 'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}'
            yield "data: [DONE]"

    def fake_post(url, headers=None, json=None, timeout=None, stream=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        captured["stream"] = stream
        return FakeResponse()

    monkeypatch.setattr("llm.deepseek_client.requests.post", fake_post)

    client = DeepSeekClient(api_key="test-key")
    events = list(client.stream([{"role": "user", "content": "Hello"}]))

    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["stream"] is True
    assert captured["json"]["stream"] is True
    assert events == [
        {"type": "content_delta", "text": "Hello"},
        {"type": "content_delta", "text": " world"},
        {"type": "message_finished", "finish_reason": "stop"},
    ]


def test_deepseek_client_stream_yields_tool_call_events(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def iter_lines(self, decode_unicode=True):
            yield "data: " + json.dumps(
                {
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "id": "call_1",
                                        "type": "function",
                                        "function": {"name": "search_jobs", "arguments": ""},
                                    }
                                ]
                            }
                        }
                    ]
                }
            )
            yield "data: " + json.dumps(
                {
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "function": {"arguments": '{"keyword": "lang'},
                                    }
                                ]
                            }
                        }
                    ]
                }
            )
            yield "data: " + json.dumps(
                {
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "function": {"arguments": 'graph"}'},
                                    }
                                ]
                            },
                            "finish_reason": "tool_calls",
                        }
                    ]
                }
            )
            yield "data: [DONE]"

    monkeypatch.setattr("llm.deepseek_client.requests.post", lambda *args, **kwargs: FakeResponse())

    client = DeepSeekClient(api_key="test-key")
    events = list(
        client.stream(
            [{"role": "user", "content": "Find jobs"}],
            tools=[{"type": "function", "function": {"name": "search_jobs"}}],
        )
    )

    assert events[0] == {
        "type": "tool_call_delta",
        "index": 0,
        "id": "call_1",
        "name": "search_jobs",
        "arguments_delta": "",
    }
    assert events[1]["type"] == "tool_call_delta"
    assert events[2] == {
        "type": "tool_call_delta",
        "index": 0,
        "id": "call_1",
        "name": "search_jobs",
        "arguments_delta": 'graph"}',
    }
    assert events[3] == {
        "type": "tool_call_finished",
        "index": 0,
        "id": "call_1",
        "name": "search_jobs",
        "arguments": '{"keyword": "langgraph"}',
    }
    assert events[4] == {"type": "message_finished", "finish_reason": "tool_calls"}


def test_deepseek_client_stream_raises_clear_error_for_invalid_sse_json(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def iter_lines(self, decode_unicode=True):
            yield "data: {not-json}"

    monkeypatch.setattr("llm.deepseek_client.requests.post", lambda *args, **kwargs: FakeResponse())

    client = DeepSeekClient(api_key="test-key")

    with pytest.raises(ValueError) as exc:
        list(client.stream([{"role": "user", "content": "Hello"}]))

    assert "stream" in str(exc.value).lower()
    assert "json" in str(exc.value).lower()
