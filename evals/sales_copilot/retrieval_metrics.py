from __future__ import annotations

from collections.abc import Mapping


def recall_at_k(expected_ids: list[int], ranked_ids: list[int], k: int) -> float:
    if k <= 0 or not expected_ids or not ranked_ids:
        return 0.0

    expected_set = set(expected_ids)
    for ranked_id in ranked_ids[:k]:
        if ranked_id in expected_set:
            return 1.0
    return 0.0


def reciprocal_rank(expected_ids: list[int], ranked_ids: list[int]) -> float:
    if not expected_ids or not ranked_ids:
        return 0.0

    expected_set = set(expected_ids)
    for rank, ranked_id in enumerate(ranked_ids, start=1):
        if ranked_id in expected_set:
            return 1.0 / rank
    return 0.0


def _score_value(row: Mapping[str, object], key: str) -> float:
    value = row.get(key, 0.0)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return float(value)


def _summarize_rows(rows: list[dict[str, object]]) -> dict[str, float]:
    total = len(rows)
    if total == 0:
        return {
            "recall_at_1": 0.0,
            "recall_at_3": 0.0,
            "recall_at_5": 0.0,
            "mrr": 0.0,
        }

    return {
        "recall_at_1": sum(_score_value(row, "recall_at_1") for row in rows) / total,
        "recall_at_3": sum(_score_value(row, "recall_at_3") for row in rows) / total,
        "recall_at_5": sum(_score_value(row, "recall_at_5") for row in rows) / total,
        "mrr": sum(_score_value(row, "mrr") for row in rows) / total,
    }


def summarize_retrieval_metrics(rows_by_mode: dict[str, list[dict]]) -> dict[str, dict]:
    return {mode: _summarize_rows(rows) for mode, rows in rows_by_mode.items()}


def summarize_retrieval_metrics_by_bucket(rows_by_mode: dict[str, list[dict]]) -> dict[str, dict[str, dict[str, float]]]:
    bucketed: dict[str, dict[str, list[dict[str, object]]]] = {}

    for mode, rows in rows_by_mode.items():
        mode_buckets: dict[str, list[dict[str, object]]] = {}
        for row in rows:
            case_type = row.get("case_type")
            if not isinstance(case_type, str) or not case_type:
                continue
            mode_buckets.setdefault(case_type, []).append(row)
        bucketed[mode] = {bucket: _summarize_rows(bucket_rows) for bucket, bucket_rows in mode_buckets.items()}

    return bucketed
