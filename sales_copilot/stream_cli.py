from __future__ import annotations

import json
from typing import Any


def render_stream_event(event: dict[str, Any]) -> str:
    event_type = event.get("type")
    if event_type == "workflow_started":
        return f"[workflow started] {event.get('workflow_name')} ({event.get('execution_mode')})"
    if event_type == "node_started":
        return f"[node started] {event.get('node')} stream={event.get('streaming')}"
    if event_type == "content_delta":
        return str(event.get("text", ""))
    if event_type == "tool_call_delta":
        return f"[tool delta] {event.get('node')} -> {event.get('name')} {event.get('arguments_delta', '')}"
    if event_type == "tool_call_finished":
        return f"[tool] {event.get('node')} -> {event.get('name')} {event.get('arguments', '')}"
    if event_type == "state_patch":
        patch = json.dumps(event.get("patch", {}), ensure_ascii=False)
        return f"[state patch] {event.get('node')} {patch}"
    if event_type == "node_finished":
        return f"[node finished] {event.get('node')}"
    if event_type == "message_finished":
        return f"[message finished] {event.get('node')} ({event.get('finish_reason')})"
    if event_type == "workflow_finished":
        return "[workflow finished]"
    if event_type == "error":
        return f"[error] {event.get('node')}: {event.get('message')}"
    return json.dumps(event, ensure_ascii=False)
