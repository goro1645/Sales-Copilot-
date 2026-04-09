from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evals.sales_copilot.retrieval_runner import run_dual_path_retrieval_benchmark, run_retrieval_benchmark
from llm.deepseek_client import DeepSeekClient


def _default_cases_path() -> Path:
    return REPO_ROOT / "evals" / "sales_copilot" / "retrieval_cases.jsonl"


def _build_report_markdown(payload: dict[str, Any]) -> str:
    config = payload.get("config", {})
    reranker_model = None
    if isinstance(config, dict):
        candidate = config.get("reranker_model")
        if isinstance(candidate, str) and candidate.strip():
            reranker_model = candidate.strip()

    if payload.get("report_kind") == "dual_path":
        summary = payload.get("summary", {})
        bucket_summary = payload.get("bucket_summary", {})
        gap = payload.get("gap", {})
        lines = [
            "# Sales Copilot Dual-Path Retrieval Eval Report",
            "",
            "## Config",
            "",
            f"- Reranker Model: `{reranker_model or 'none'}`",
            "",
            "## Gold Retrieval",
            "",
            json.dumps(summary.get("gold", {}), ensure_ascii=False, indent=2),
            "",
            "## Model Retrieval",
            "",
            json.dumps(summary.get("model", {}), ensure_ascii=False, indent=2),
            "",
            "## Bucket Summary",
            "",
            json.dumps(bucket_summary, ensure_ascii=False, indent=2),
            "",
            "## Gap Analysis",
            "",
            json.dumps(gap, ensure_ascii=False, indent=2),
        ]
        return "\n".join(lines)

    summary = payload.get("summary", {})
    bucket_summary = payload.get("bucket_summary", {})
    case_results = payload.get("case_results", [])
    lines = [
        "# Sales Copilot Retrieval Eval Report",
        "",
        "## Config",
        "",
        f"- Reranker Model: `{reranker_model or 'none'}`",
        "",
        "## Summary",
        "",
        "| mode | value |",
        "| --- | --- |",
    ]
    if isinstance(summary, dict):
        for mode, mode_summary in summary.items():
            lines.append(f"| {mode} | {json.dumps(mode_summary, ensure_ascii=False)} |")
    lines.extend(
        [
            "",
            "## Bucket Summary",
            "",
            "| mode | case_type | value |",
            "| --- | --- | --- |",
        ]
    )
    if isinstance(bucket_summary, dict):
        for mode, mode_buckets in bucket_summary.items():
            if not isinstance(mode_buckets, dict):
                continue
            for case_type, bucket_metrics in mode_buckets.items():
                lines.append(f"| {mode} | {case_type} | {json.dumps(bucket_metrics, ensure_ascii=False)} |")
    lines.extend(
        [
            "",
            "## Case Results",
            "",
            "| case_id | case_type | query_origin |",
            "| --- | --- | --- |",
        ]
    )
    for row in case_results:
        if isinstance(row, dict):
            case_id = row.get("case_id", "unknown")
            case_type = row.get("case_type", "unknown")
            query_origin = row.get("query_origin", "unknown")
        else:
            case_id = "unknown"
            case_type = "unknown"
            query_origin = "unknown"
        lines.append(f"| {case_id} | {case_type} | {query_origin} |")
    return "\n".join(lines)


def write_retrieval_report(*, output_dir: Path | str, payload: dict[str, Any]) -> dict[str, Path]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    report_json = output_path / "report.json"
    report_md = output_path / "report.md"
    case_results_jsonl = output_path / "case_results.jsonl"

    report_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report_md.write_text(_build_report_markdown(payload), encoding="utf-8")
    with case_results_jsonl.open("w", encoding="utf-8") as handle:
        for row in payload.get("case_results", []):
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    return {
        "report_dir": output_path,
        "report_json": report_json,
        "report_md": report_md,
        "case_results_jsonl": case_results_jsonl,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Sales Copilot retrieval benchmark.")
    parser.add_argument("--cases", default=None, help="Path to the retrieval cases JSONL file.")
    parser.add_argument("--db-path", required=True, help="Path to the knowledge base database.")
    parser.add_argument("--output-dir", required=True, help="Directory for timestamped evaluation reports.")
    parser.add_argument("--benchmark-kind", choices=["single", "dual"], default="single")
    parser.add_argument("--csds-data-dir", default=os.getenv("CSDS_DATA_DIR", ""))
    parser.add_argument("--api-base-url", default=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
    parser.add_argument("--api-model", default=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    cases_path = Path(args.cases) if args.cases else _default_cases_path()
    db_path = Path(args.db_path)
    output_root = Path(args.output_dir)

    if args.benchmark_kind == "dual":
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        if not api_key:
            raise SystemExit("Missing DeepSeek API key. Set DEEPSEEK_API_KEY.")
        if not args.csds_data_dir:
            raise SystemExit("Missing CSDS data dir. Set --csds-data-dir or CSDS_DATA_DIR.")
        payload = run_dual_path_retrieval_benchmark(
            cases_path=cases_path,
            db_path=db_path,
            llm_client=DeepSeekClient(api_key=api_key, base_url=args.api_base_url, model=args.api_model),
            csds_data_dir=args.csds_data_dir,
        )
    else:
        payload = run_retrieval_benchmark(cases_path=cases_path, db_path=db_path)
    report_dir = output_root / dt.datetime.now().strftime("%Y%m%d%H%M%S")
    paths = write_retrieval_report(output_dir=report_dir, payload=payload)

    print(f"Evaluated {len(payload.get('case_results', []))} cases.")
    print(f"report_dir: {paths['report_dir']}")
    print(f"report.json: {paths['report_json']}")
    print(f"report.md: {paths['report_md']}")
    print(f"case_results.jsonl: {paths['case_results_jsonl']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
