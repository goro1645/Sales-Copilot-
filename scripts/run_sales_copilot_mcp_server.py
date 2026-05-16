from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import anyio

if __package__ is None or __package__ == "":
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sales_copilot.mcp_stdio_server import build_stdio_server


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Sales Copilot stdio MCP server.")
    parser.add_argument(
        "--db-path",
        default=str(Path(__file__).resolve().parents[1] / "data" / "sales_copilot" / "sales_copilot.db"),
        help="Path to the SQLite database used by the CRM/Tasks tools.",
    )
    return parser.parse_args()


async def _main() -> None:
    args = parse_args()
    server = build_stdio_server(args.db_path)
    await server.run_stdio_async()


if __name__ == "__main__":
    anyio.run(_main)
