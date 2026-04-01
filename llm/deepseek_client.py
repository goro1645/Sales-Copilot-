from typing import Any

import requests

from .base import BaseLLMClient


class DeepSeekClient(BaseLLMClient):
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def complete(
        self,
        messages: list[dict],
        response_format: dict | None = None,
    ) -> str:
        url = f"{self.base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": list(messages),
            "temperature": 0.2,
            "stream": False,
        }
        if response_format is not None:
            payload["response_format"] = response_format

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        response = requests.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        return self._extract_content(data)

    def _extract_content(self, data: Any) -> str:
        if not isinstance(data, dict):
            raise ValueError("DeepSeek response must be a dict with choices")

        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("DeepSeek response has empty or invalid choices")

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise ValueError("DeepSeek response choice must be a dict")

        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise ValueError("DeepSeek response choice is missing message")

        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("DeepSeek response message is missing content")

        return content
