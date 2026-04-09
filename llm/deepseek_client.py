from __future__ import annotations

import json
from typing import Any, Iterable

import requests

from .base import BaseLLMClient
from .streaming import StreamToolCallAssembler


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

        response = requests.post(url, headers=self._headers(), json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        return self._extract_content(data)

    def stream(self, messages: list[dict], tools: list[dict] | None = None):
        """消费 DeepSeek 官方 SSE，并规范化成 provider-agnostic 事件。"""

        url = f"{self.base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": list(messages),
            "temperature": 0.2,
            "stream": True,
        }
        if tools:
            payload["tools"] = list(tools)

        response = requests.post(
            url,
            headers=self._headers(),
            json=payload,
            timeout=120,
            stream=True,
        )
        response.raise_for_status()

        tool_assembler = StreamToolCallAssembler()

        for payload_chunk in self._iter_sse_payloads(response.iter_lines(decode_unicode=True)):
            if payload_chunk == "[DONE]":
                break

            choices = payload_chunk.get("choices")
            if not isinstance(choices, list):
                raise ValueError("DeepSeek stream response has invalid choices shape")

            for choice in choices:
                if not isinstance(choice, dict):
                    raise ValueError("DeepSeek stream response choice must be a dict")

                delta = choice.get("delta") or {}
                if not isinstance(delta, dict):
                    raise ValueError("DeepSeek stream delta must be a dict")

                content = delta.get("content")
                if isinstance(content, str) and content:
                    yield {"type": "content_delta", "text": content}

                tool_calls = delta.get("tool_calls")
                if isinstance(tool_calls, list):
                    for tool_call in tool_calls:
                        if not isinstance(tool_call, dict):
                            continue
                        function = tool_call.get("function") or {}
                        yield from tool_assembler.push_delta(
                            index=tool_call.get("index", 0),
                            tool_id=tool_call.get("id"),
                            name=function.get("name"),
                            arguments_delta=function.get("arguments"),
                        )

                finish_reason = choice.get("finish_reason")
                if finish_reason == "tool_calls":
                    for index in tool_assembler.active_indexes():
                        yield tool_assembler.finish(index=index)
                    yield {"type": "message_finished", "finish_reason": "tool_calls"}
                elif isinstance(finish_reason, str) and finish_reason:
                    yield {"type": "message_finished", "finish_reason": finish_reason}

    def _iter_sse_payloads(self, lines: Iterable[str]):
        for raw_line in lines:
            if raw_line is None:
                continue
            line = raw_line.strip()
            if not line:
                continue
            if not line.startswith("data:"):
                continue

            payload_text = line[5:].strip()
            if payload_text == "[DONE]":
                yield "[DONE]"
                continue

            try:
                yield json.loads(payload_text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"DeepSeek stream returned invalid JSON: {payload_text}") from exc

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

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
