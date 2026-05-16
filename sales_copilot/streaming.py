from __future__ import annotations

from typing import Any


def make_workflow_started_event(workflow_name: str, execution_mode: str) -> dict[str, Any]:
    return {
        "type": "workflow_started",
        "workflow_name": workflow_name,
        "execution_mode": execution_mode,
    }


def make_workflow_finished_event(result: dict[str, Any]) -> dict[str, Any]:
    return {"type": "workflow_finished", "result": result}


def make_node_started_event(node: str, streaming: bool) -> dict[str, Any]:
    return {"type": "node_started", "node": node, "streaming": streaming}


def make_node_finished_event(node: str) -> dict[str, Any]:
    return {"type": "node_finished", "node": node}


def make_content_delta_event(node: str, text: str) -> dict[str, Any]:
    return {"type": "content_delta", "node": node, "text": text}


def make_message_finished_event(node: str, finish_reason: str) -> dict[str, Any]:
    return {"type": "message_finished", "node": node, "finish_reason": finish_reason}


def make_state_patch_event(node: str, patch: dict[str, Any]) -> dict[str, Any]:
    return {"type": "state_patch", "node": node, "patch": patch}


def make_error_event(node: str, message: str) -> dict[str, Any]:
    return {"type": "error", "node": node, "message": message}


def _with_node(event: dict[str, Any], node: str) -> dict[str, Any]:
    enriched = dict(event)
    enriched["node"] = node
    return enriched


def stream_llm_completion(
    *,
    llm_client,
    node: str,
    messages: list[dict[str, Any]],
    response_format: dict[str, Any] | None = None,
    tools: list[dict[str, Any]] | None = None,
):
    stream_method = getattr(llm_client, "stream", None)
    if callable(stream_method):
        iterator = None
        try:
            iterator = stream_method(messages, tools=tools, response_format=response_format)
        except TypeError:
            try:
                iterator = stream_method(messages, tools=tools)
            except TypeError:
                iterator = stream_method(messages)
        except NotImplementedError:
            iterator = None
        if iterator is not None:
            content_parts: list[str] = []
            saw_message_finished = False
            for raw_event in iterator:
                if not isinstance(raw_event, dict):
                    continue
                event_type = raw_event.get("type")
                if event_type == "content_delta":
                    text = str(raw_event.get("text", ""))
                    content_parts.append(text)
                    yield make_content_delta_event(node, text)
                elif event_type in {"tool_call_delta", "tool_call_finished"}:
                    yield _with_node(raw_event, node)
                elif event_type == "message_finished":
                    saw_message_finished = True
                    yield make_message_finished_event(node, str(raw_event.get("finish_reason", "stop")))
            if not saw_message_finished:
                yield make_message_finished_event(node, "stop")
            return "".join(content_parts)

    content = llm_client.complete(messages, response_format=response_format)
    if content:
        yield make_content_delta_event(node, content)
    yield make_message_finished_event(node, "stop")
    return content
