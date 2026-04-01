from llm import BaseLLMClient, DeepSeekClient


def test_deepseek_client_exports_base_class_and_client():
    assert BaseLLMClient is not None
    assert DeepSeekClient is not None


def test_deepseek_client_posts_to_chat_completions_and_returns_message(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    def fake_post(url, headers=None, json=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setattr("llm.deepseek_client.requests.post", fake_post)

    client = DeepSeekClient(api_key="test-key")
    result = client.complete([{"role": "user", "content": "Hello"}])

    assert result == "ok"
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["json"]["model"] == "deepseek-chat"
    assert captured["json"]["messages"] == [{"role": "user", "content": "Hello"}]


def test_deepseek_client_forwards_response_format(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "structured"}}]}

    def fake_post(url, headers=None, json=None):
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setattr("llm.deepseek_client.requests.post", fake_post)

    client = DeepSeekClient(api_key="test-key", base_url="https://api.deepseek.com")
    result = client.complete(
        [{"role": "user", "content": "Hello"}],
        response_format={"type": "json_object"},
    )

    assert result == "structured"
    assert captured["json"]["response_format"] == {"type": "json_object"}
