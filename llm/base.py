from abc import ABC, abstractmethod


class BaseLLMClient(ABC):
    """最小的 LLM client 接口。

    `complete(...)` 继续服务现有非流式路径；
    `stream(...)` 是可选能力，只给需要官方 SSE 的 provider 实现。
    """

    @abstractmethod
    def complete(
        self,
        messages: list[dict],
        response_format: dict | None = None,
    ) -> str:
        """发送消息并返回完整文本结果。"""

    def stream(self, messages: list[dict], tools: list[dict] | None = None):
        """可选的流式接口，默认不实现。"""

        raise NotImplementedError("This LLM client does not implement streaming")
