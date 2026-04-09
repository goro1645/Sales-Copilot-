from __future__ import annotations


class StreamToolCallAssembler:
    """把多段 tool-call delta 组装成完整工具调用。

    DeepSeek/OpenAI 风格的流式 tool call 经常会把：
    - tool id
    - function name
    - arguments 字符串
    拆成多个 chunk 返回。

    这个类只负责把这些碎片重新拼回一个稳定的事件流，
    这样上层 client 和 demo 不需要自己维护临时状态。
    """

    def __init__(self) -> None:
        self._calls: dict[int, dict] = {}

    def push_delta(
        self,
        *,
        index: int,
        tool_id: str | None,
        name: str | None,
        arguments_delta: str | None,
    ) -> list[dict]:
        call_state = self._calls.setdefault(
            index,
            {"id": tool_id, "name": name, "arguments_parts": []},
        )
        if tool_id:
            call_state["id"] = tool_id
        if name:
            call_state["name"] = name
        if arguments_delta is not None:
            call_state["arguments_parts"].append(arguments_delta)

        return [
            {
                "type": "tool_call_delta",
                "index": index,
                "id": call_state["id"],
                "name": call_state["name"],
                "arguments_delta": arguments_delta or "",
            }
        ]

    def finish(self, *, index: int) -> dict:
        call_state = self._calls[index]
        return {
            "type": "tool_call_finished",
            "index": index,
            "id": call_state["id"],
            "name": call_state["name"],
            "arguments": "".join(call_state["arguments_parts"]),
        }

    def active_indexes(self) -> list[int]:
        return sorted(self._calls.keys())
