from abc import ABC, abstractmethod
from typing import Any


class BaseLLMClient(ABC):
    """最小的模型调用接口，方便以后替换 provider。"""

    @abstractmethod
    def complete(
        self,
        messages: list[dict],
        response_format: dict | None = None,
    ) -> str:
        """把对话消息发给模型，并返回纯文本结果。"""
