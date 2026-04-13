from __future__ import annotations

import json
from typing import Any, Iterable


def encode_sse_event(event: dict[str, Any]) -> str:
    return f"event: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"


def iter_sse_events(events: Iterable[dict[str, Any]]):
    for event in events:
        yield encode_sse_event(event)
