from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evals.sales_copilot.gold_audit import generate_full_csds_gold_audit


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a stratified full-CSDS gold audit sample.")
    parser.add_argument("--csds-data-dir", required=True)
    parser.add_argument("--split", default="test")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--ordinary-count", type=int, default=15)
    parser.add_argument("--timeline-count", type=int, default=15)
    parser.add_argument("--budget-count", type=int, default=10)
    parser.add_argument("--overlap-count", type=int, default=10)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows, summary = generate_full_csds_gold_audit(
        Path(args.csds_data_dir),
        split=args.split,
        bucket_targets={
            "ordinary": args.ordinary_count,
            "timeline_nonempty": args.timeline_count,
            "budget_nonempty": args.budget_count,
            "field_overlap_high_risk": args.overlap_count,
        },
    )

    sample_path = output_dir / "full_csds_gold_audit_sample.jsonl"
    summary_path = output_dir / "full_csds_gold_audit_summary.json"

    with sample_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"sample_path: {sample_path}")
    print(f"summary_path: {summary_path}")
    print(f"sample_size: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
