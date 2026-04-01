from llm import BaseLLMClient, DeepSeekClient
import inspect


def test_deepseek_client_exports_base_class_and_client():
    assert BaseLLMClient is not None
    assert DeepSeekClient is not None
    assert str(inspect.signature(BaseLLMClient.complete)) == "(self, messages: list[dict], response_format: dict | None = None) -> str"


def test_deepseek_client_posts_to_chat_completions_and_returns_message(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("llm.deepseek_client.requests.post", fake_post)

    client = DeepSeekClient(api_key="test-key")
    result = client.complete([{"role": "user", "content": "Hello"}])

    assert result == "ok"
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["json"]["model"] == "deepseek-chat"
    assert captured["json"]["messages"] == [{"role": "user", "content": "Hello"}]
    assert captured["json"]["temperature"] == 0.2
    assert captured["json"]["stream"] is False
    assert captured["timeout"] == 120


def test_deepseek_client_forwards_response_format(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "structured"}}]}

    def fake_post(url, headers=None, json=None, timeout=None):
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


def test_deepseek_client_raises_clear_error_for_empty_choices(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": []}

    monkeypatch.setattr("llm.deepseek_client.requests.post", lambda *args, **kwargs: FakeResponse())

    client = DeepSeekClient(api_key="test-key")

    try:
        client.complete([{"role": "user", "content": "Hello"}])
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "choices" in str(exc).lower()
        assert "empty" in str(exc).lower()


def test_deepseek_client_raises_clear_error_for_missing_content(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {}}]}

    monkeypatch.setattr("llm.deepseek_client.requests.post", lambda *args, **kwargs: FakeResponse())

    client = DeepSeekClient(api_key="test-key")

    try:
        client.complete([{"role": "user", "content": "Hello"}])
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "content" in str(exc).lower()
        assert "missing" in str(exc).lower()


def test_deepseek_client_raises_clear_error_for_unexpected_response_shape(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return ["not", "a", "dict"]

    monkeypatch.setattr("llm.deepseek_client.requests.post", lambda *args, **kwargs: FakeResponse())

    client = DeepSeekClient(api_key="test-key")

    try:
        client.complete([{"role": "user", "content": "Hello"}])
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "response" in str(exc).lower()
        assert "dict" in str(exc).lower()
