from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evals.sales_copilot.artificial_sales_workflow_benchmark import (
    author_sales_cases,
    build_sales_case_blueprints,
    write_artificial_sales_readme,
)
from evals.sales_copilot.workflow_calibrated_benchmark import write_jsonl
from llm.deepseek_client import DeepSeekClient


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build an artificial sales workflow benchmark draft.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--api-key", default="")
    parser.add_argument("--api-base-url", default=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
    parser.add_argument("--api-model", default=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"))
    parser.add_argument("--limit", type=int, default=50)
    return parser


def _build_deepseek_client(api_key: str, base_url: str, model: str):
    return DeepSeekClient(api_key=api_key, base_url=base_url, model=model)


def main() -> int:
    args = _build_parser().parse_args()
    api_key = str(args.api_key or os.environ.get("DEEPSEEK_API_KEY", "")).strip()
    if not api_key:
        raise SystemExit("Missing DeepSeek API key. Pass --api-key or set DEEPSEEK_API_KEY.")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    blueprints = build_sales_case_blueprints()[: max(0, args.limit)]
    client = _build_deepseek_client(api_key, args.api_base_url, args.api_model)
    rows = author_sales_cases(blueprints, llm_client=client)

    jsonl_path = output_dir / "artificial_sales_workflow_benchmark_50.jsonl"
    readme_path = output_dir / "artificial_sales_workflow_benchmark_50_README.md"
    write_jsonl(jsonl_path, rows)
    write_artificial_sales_readme(readme_path, rows)

    print(f"Built {len(rows)} artificial sales workflow benchmark rows.")
    print(f"final_jsonl: {jsonl_path}")
    print(f"readme_md: {readme_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

