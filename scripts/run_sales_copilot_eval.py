from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evals.sales_copilot.reporting import write_report_bundle
from evals.sales_copilot.runner import run_offline_evaluation
from llm.deepseek_client import DeepSeekClient


def _default_cases_path() -> Path:
    return REPO_ROOT / "evals" / "sales_copilot" / "golden_cases.jsonl"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Sales Copilot offline evaluation.")
    parser.add_argument("--cases", default=str(_default_cases_path()))
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--mode", choices=["offline"], default="offline")
    parser.add_argument("--api-base-url", default=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
    parser.add_argument("--api-model", default=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise SystemExit("Missing DeepSeek API key. Set DEEPSEEK_API_KEY.")

    llm_client = DeepSeekClient(
        api_key=api_key,
        base_url=args.api_base_url,
        model=args.api_model,
    )
    bundle = run_offline_evaluation(
        cases_path=args.cases,
        output_dir=args.output_dir,
        llm_client=llm_client,
    )
    report_dir = Path(write_report_bundle(bundle, args.output_dir))

    print(f"Evaluated {bundle['summary']['total_cases']} cases.")
    print(f"report_dir: {report_dir}")
    print(f"report.json: {report_dir / 'report.json'}")
    print(f"report.md: {report_dir / 'report.md'}")
    print(f"case_results.jsonl: {report_dir / 'case_results.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
