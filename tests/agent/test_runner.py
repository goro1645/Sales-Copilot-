from agent.runner import MiniMindAPIGenerator


class DummyResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_minimind_api_generator_reads_chat_completion_content(monkeypatch):
    captured = {}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return DummyResponse(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Generated resume rewrite",
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("agent.runner.requests.post", fake_post)

    generator = MiniMindAPIGenerator(
        base_url="http://127.0.0.1:8998/v1",
        api_key="minimind",
        model="minimind",
    )
    result = generator.rewrite_resume(
        role="LLM Application Engineer",
        resume_text="Built MiniMind APIs with Python and FastAPI.",
        required_skills=["python", "fastapi"],
        matched_skills=["python", "fastapi"],
        missing_skills=[],
    )

    assert result == "Generated resume rewrite"
    assert captured["url"] == "http://127.0.0.1:8998/v1/chat/completions"
    assert captured["json"]["model"] == "minimind"
    assert captured["json"]["messages"][0]["role"] == "system"
    assert captured["timeout"] == 120
