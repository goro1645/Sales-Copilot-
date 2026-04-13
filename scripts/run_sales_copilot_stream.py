from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

__package__ = "scripts"
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from llm.deepseek_client import DeepSeekClient
from sales_copilot.runner import run_sales_copilot, run_sales_copilot_stream
from sales_copilot.stream_cli import render_stream_event


def _read_text(raw_value: str) -> str:
    candidate = Path(raw_value)
    if candidate.exists() and candidate.is_file():
        return candidate.read_text(encoding="utf-8")
    return raw_value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Sales Copilot workflow.")
    parser.add_argument("--customer-profile", required=True, help="Customer profile text or a file path")
    parser.add_argument("--meeting-note", required=True, help="Meeting note text or a file path")
    parser.add_argument("--database-path", default="data/sales_copilot/sales_copilot.db")
    parser.add_argument("--execution-mode", choices=["direct", "mcp"], default="direct")
    parser.add_argument("--api-base-url", default=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
    parser.add_argument("--api-model", default=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"))
    parser.add_argument("--stream", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise SystemExit("Missing DeepSeek API key. Set DEEPSEEK_API_KEY.")

    client = DeepSeekClient(api_key=api_key, base_url=args.api_base_url, model=args.api_model)
    customer_profile_text = _read_text(args.customer_profile)
    meeting_note_text = _read_text(args.meeting_note)

    if args.stream:
        final_result = None
        for event in run_sales_copilot_stream(
            customer_profile_text=customer_profile_text,
            meeting_note_text=meeting_note_text,
            database_path=args.database_path,
            llm_client=client,
            execution_mode=args.execution_mode,
        ):
            print(render_stream_event(event))
            if event.get("type") == "workflow_finished":
                final_result = event.get("result")
        if final_result is not None:
            print(json.dumps(final_result.get("dashboard_output", {}), ensure_ascii=False, indent=2))
        return 0

    result = run_sales_copilot(
        customer_profile_text=customer_profile_text,
        meeting_note_text=meeting_note_text,
        database_path=args.database_path,
        llm_client=client,
        execution_mode=args.execution_mode,
    )
    print(json.dumps(result.get("dashboard_output", {}), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
