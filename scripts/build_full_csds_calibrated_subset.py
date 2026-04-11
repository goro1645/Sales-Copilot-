from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evals.sales_copilot.calibrated_subset import (
    build_calibrated_sample,
    build_calibrated_working_rows,
    export_final_calibrated_rows,
    load_case_results_by_id,
    write_jsonl,
)
from evals.sales_copilot.csds_adapter import load_full_csds_cases


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a calibrated full-CSDS subset for human review.")
    parser.add_argument("--csds-data-dir", default="")
    parser.add_argument("--split", default="test")
    parser.add_argument("--baseline-case-results", default="")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--export-final-from-working", default="")
    return parser


def _load_raw_split_rows(dataset_dir: Path, split: str) -> dict[str, dict[str, Any]]:
    split_path = Path(dataset_dir) / f"{split}.json"
    payload = json.loads(split_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"split file must contain a JSON list: {split_path}")
    rows: dict[str, dict[str, Any]] = {}
    for row in payload:
        if not isinstance(row, dict):
            continue
        dialogue_id = str(row.get("DialogueID", "")).strip()
        if dialogue_id:
            rows[dialogue_id] = row
    return rows


def _read_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def _attach_raw_rows(
    cases: list[dict[str, object]],
    raw_rows_by_uid: dict[str, dict[str, Any]],
) -> list[dict[str, object]]:
    enriched: list[dict[str, object]] = []
    for case in cases:
        row = dict(case)
        source_uid = str(case.get("source_uid", ""))
        row["_raw_row"] = raw_rows_by_uid.get(source_uid, {})
        enriched.append(row)
    return enriched


def main() -> int:
    args = _build_parser().parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.export_final_from_working:
        working_rows = _read_jsonl_rows(Path(args.export_final_from_working))
        final_rows = export_final_calibrated_rows(working_rows)
        write_jsonl(output_dir / "full_csds_calibrated_100.jsonl", final_rows)
        print(f"Exported {len(final_rows)} calibrated rows.")
        print(f"final_jsonl: {output_dir / 'full_csds_calibrated_100.jsonl'}")
        return 0

    if not args.csds_data_dir:
        raise SystemExit("Missing CSDS data dir. Set --csds-data-dir.")
    if not args.baseline_case_results:
        raise SystemExit("Missing baseline case results. Set --baseline-case-results.")

    cases = load_full_csds_cases(Path(args.csds_data_dir), splits=[str(args.split)])
    raw_rows_by_uid = _load_raw_split_rows(Path(args.csds_data_dir), str(args.split))
    baseline_case_results = load_case_results_by_id(Path(args.baseline_case_results))

    sample_cases = build_calibrated_sample(
        _attach_raw_rows(cases, raw_rows_by_uid),
        baseline_case_results=baseline_case_results,
    )
    working_rows = build_calibrated_working_rows(
        sample_cases,
        baseline_case_results=baseline_case_results,
    )

    working_path = output_dir / "full_csds_calibration_working_100.jsonl"
    write_jsonl(working_path, working_rows)

    bucket_counts: dict[str, int] = {}
    review_needed_count = 0
    for row in working_rows:
        bucket = str(row.get("sampling_bucket", "unknown"))
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1
        pre_annotation = row.get("pre_annotation", {})
        if isinstance(pre_annotation, dict) and pre_annotation.get("needs_human_review", False):
            review_needed_count += 1

    print(f"Built {len(working_rows)} calibration rows.")
    print(f"working_jsonl: {working_path}")
    print(f"bucket_counts: {bucket_counts}")
    print(f"needs_human_review: {review_needed_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
