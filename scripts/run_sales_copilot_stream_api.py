from __future__ import annotations

import argparse
import os
import sys

import uvicorn

__package__ = "scripts"
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sales_copilot.stream_api import create_sales_copilot_stream_app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Sales Copilot streaming API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8011, type=int)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    uvicorn.run(create_sales_copilot_stream_app(), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
