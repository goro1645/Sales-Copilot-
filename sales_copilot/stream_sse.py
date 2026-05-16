from __future__ import annotations

import json
from typing import Any, Iterable

from sales_copilot.streaming import make_error_event


def encode_sse_event(event: dict[str, Any]) -> str:
    return f"event: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"


def iter_sse_events(events: Iterable[dict[str, Any]]):
    saw_error_event = False
    try:
        for event in events:
            if event.get("type") == "error":
                saw_error_event = True
            yield encode_sse_event(event)
    except Exception as exc:
        if not saw_error_event:
            yield encode_sse_event(make_error_event("sales_copilot", str(exc)))
