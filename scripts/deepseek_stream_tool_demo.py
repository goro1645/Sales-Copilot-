from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

__package__ = "scripts"
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from llm.deepseek_client import DeepSeekClient
from sales_copilot import storage, tools


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "sales_copilot" / "sales_copilot.db"

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_product_knowledge",
            "description": "Search product knowledge for deployment, audit, CRM integration, and security-related questions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query for product knowledge."},
                    "top_k": {"type": "integer", "description": "Maximum number of results to return."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_sales_playbook",
            "description": "Search sales playbook guidance for discovery, follow-up, objection handling, and next-step planning.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query for playbook guidance."},
                    "top_k": {"type": "integer", "description": "Maximum number of results to return."},
                },
                "required": ["query"],
            },
        },
    },
]


def _seed_demo_knowledge(db_path: Path) -> None:
    storage.init_storage(db_path)
    tools.seed_knowledge_chunks(db_path, tools.sample_product_chunks())
    tools.seed_knowledge_chunks(db_path, tools.sample_playbook_chunks())


def _run_local_tool(db_path: Path, *, name: str, arguments_json: str) -> str:
    arguments = json.loads(arguments_json or "{}")
    query = str(arguments.get("query", "")).strip()
    top_k = int(arguments.get("top_k", 3))

    if name == "search_product_knowledge":
        rows = tools.search_product_knowledge(db_path, query=query, top_k=top_k)
    elif name == "search_sales_playbook":
        rows = tools.search_sales_playbook(db_path, query=query, top_k=top_k)
    else:
        raise ValueError(f"Unsupported tool: {name}")

    normalized = [
        {
            "source_name": row.get("source_name"),
            "chunk_text": row.get("chunk_text"),
            "matched_terms": row.get("matched_terms", []),
            "score": row.get("score", 0),
        }
        for row in rows
    ]
    return json.dumps({"results": normalized}, ensure_ascii=False)


def _stream_once(client: DeepSeekClient, *, messages: list[dict], tool_definitions: list[dict]):
    tool_calls: list[dict] = []

    for event in client.stream(messages, tools=tool_definitions):
        event_type = event["type"]
        if event_type == "content_delta":
            print(event["text"], end="", flush=True)
        elif event_type == "tool_call_delta":
            # 这里不逐字打印 arguments，避免把半截 JSON 打乱终端阅读体验。
            if event.get("name"):
                print(f"\n[tool delta] {event['name']}", flush=True)
        elif event_type == "tool_call_finished":
            print(
                f"\n[tool finished] {event['name']} arguments={event['arguments']}",
                flush=True,
            )
            tool_calls.append(event)
        elif event_type == "message_finished":
            print(f"\n[finish_reason] {event['finish_reason']}", flush=True)
        elif event_type == "error":
            print(f"\n[stream error] {event['message']}", flush=True)

    return tool_calls


def main() -> None:
    parser = argparse.ArgumentParser(description="DeepSeek streaming tool-call demo")
    parser.add_argument(
        "--prompt",
        default="Customer asks whether the product supports private deployment, audit logging, and CRM integration. Use tools if needed, then summarize the answer.",
        help="User prompt to send to DeepSeek.",
    )
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="SQLite path for local knowledge/tool data.")
    parser.add_argument("--base-url", default="https://api.deepseek.com", help="DeepSeek base URL.")
    parser.add_argument("--model", default="deepseek-chat", help="DeepSeek model name.")
    args = parser.parse_args()

    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("Please set DEEPSEEK_API_KEY before running this demo.")

    db_path = Path(args.db_path)
    _seed_demo_knowledge(db_path)

    client = DeepSeekClient(
        api_key=api_key,
        base_url=args.base_url,
        model=args.model,
    )

    messages: list[dict] = [
        {
            "role": "system",
            "content": (
                "You are a sales copilot assistant. Use tools when the user asks for product facts, "
                "deployment/security details, or sales playbook guidance. After tool use, answer clearly in Chinese."
            ),
        },
        {"role": "user", "content": args.prompt},
    ]

    print("=== First streamed pass ===")
    tool_calls = _stream_once(client, messages=messages, tool_definitions=TOOLS)

    for tool_call in tool_calls:
        tool_result = _run_local_tool(
            db_path,
            name=tool_call["name"],
            arguments_json=tool_call["arguments"],
        )
        print(f"[tool result] {tool_result}", flush=True)

        messages.append(
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": tool_call["id"] or f"call_{tool_call['index']}",
                        "type": "function",
                        "function": {
                            "name": tool_call["name"],
                            "arguments": tool_call["arguments"],
                        },
                    }
                ],
            }
        )
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call["id"] or f"call_{tool_call['index']}",
                "content": tool_result,
            }
        )

    if tool_calls:
        print("\n=== Second streamed pass (tool result incorporated) ===")
        _stream_once(client, messages=messages, tool_definitions=TOOLS)


if __name__ == "__main__":
    main()
