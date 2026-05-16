from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evals.sales_copilot.workflow_calibrated_benchmark import (
    build_workflow_calibrated_sample,
    export_final_workflow_calibrated_rows,
    fill_ai_workflow_review_rows,
    load_jsonl_rows,
    write_jsonl,
    write_workflow_readme,
)
from llm.deepseek_client import DeepSeekClient


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a workflow-calibrated Sales Copilot benchmark draft.")
    parser.add_argument(
        "--source-jsonl",
        default=str(
            REPO_ROOT
            / "evals"
            / "sales_copilot"
            / "outputs_csds_calibrated_100"
            / "full_csds_ai_calibrated_100.jsonl"
        ),
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--api-key", default="")
    parser.add_argument("--api-base-url", default=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
    parser.add_argument("--api-model", default=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"))
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

    rows = load_jsonl_rows(Path(args.source_jsonl))
    sampled_rows = build_workflow_calibrated_sample(rows)
    client = _build_deepseek_client(api_key, args.api_base_url, args.api_model)
    reviewed_rows = fill_ai_workflow_review_rows(sampled_rows, llm_client=client)
    final_rows = export_final_workflow_calibrated_rows(reviewed_rows)

    final_path = output_dir / "full_csds_workflow_calibrated_30.jsonl"
    readme_path = output_dir / "full_csds_workflow_calibrated_30_README.md"
    write_jsonl(final_path, final_rows)
    write_workflow_readme(readme_path, final_rows)

    print(f"Built {len(final_rows)} workflow-calibrated rows.")
    print(f"final_jsonl: {final_path}")
    print(f"readme_md: {readme_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
