from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Sequence


class BaseLLMClient(ABC):
    """最小的模型调用接口，方便以后替换 provider。"""

    @abstractmethod
    def complete(
        self,
        messages: Sequence[dict[str, Any]],
        response_format: dict[str, Any] | None = None,
    ) -> str:
        """把对话消息发给模型，并返回纯文本结果。"""

