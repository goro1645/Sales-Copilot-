from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict, cast

from evals.sales_copilot.retrieval_metrics import (
    recall_at_k,
    reciprocal_rank,
    summarize_retrieval_metrics_by_bucket,
    summarize_retrieval_metrics,
)
from sales_copilot import storage
from sales_copilot.retrieval import hybrid_retrieve_knowledge_chunks, hybrid_rerank_knowledge_chunks
from sales_copilot.tools import keyword_retrieve


class RetrievalCase(TypedDict):
    case_id: str
    query: str
    source_type: str
    query_origin: str
    case_type: str
    source_uid: str
    expected_chunk_ids: list[int]
    acceptable_chunk_ids: list[int]
    notes: str


class RetrievalModeResult(TypedDict):
    ranked_chunk_ids: list[int]
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    mrr: float


class RetrievalCaseResult(TypedDict):
    case_id: str
    query: str
    source_type: str
    query_origin: str
    case_type: str
    source_uid: str
    expected_chunk_ids: list[int]
    acceptable_chunk_ids: list[int]
    notes: str
    modes: dict[str, RetrievalModeResult]


_DEFAULT_TOP_K = 5
_TOP_LEVEL_FIELDS = ("case_id", "query", "source_type", "expected_chunk_ids")
_ALLOWED_SOURCE_TYPES = {"product", "playbook", "mixed"}
_ALLOWED_QUERY_ORIGINS = {"raw_user_phrase", "light_rewrite"}
_ALLOWED_CASE_TYPES = {"product_hard", "playbook_hard", "cross_source_confusing"}
_USE_DEFAULT_EMBEDDER = object()


def _ensure_object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _ensure_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def _ensure_source_type(value: object, label: str) -> str:
    source_type = _ensure_string(value, label)
    if source_type not in _ALLOWED_SOURCE_TYPES:
        raise ValueError(f"{label} must be one of {sorted(_ALLOWED_SOURCE_TYPES)}")
    return source_type


def _ensure_choice(value: object, label: str, allowed: set[str]) -> str:
    text = _ensure_string(value, label)
    if text not in allowed:
        raise ValueError(f"{label} must be one of {sorted(allowed)}")
    return text


def _ensure_expected_chunk_ids(value: object, label: str) -> list[int]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} must be a non-empty list of positive integers")

    normalized: list[int] = []
    seen: set[int] = set()
    for index, item in enumerate(value):
        if not isinstance(item, int) or isinstance(item, bool):
            raise ValueError(f"{label}[{index}] must be an integer")
        if item <= 0:
            raise ValueError(f"{label}[{index}] must be a positive integer")
        if item in seen:
            raise ValueError(f"{label} must not contain duplicate chunk ids")
        seen.add(item)
        normalized.append(item)
    return normalized


def load_retrieval_cases(path: str | Path) -> list[RetrievalCase]:
    cases: list[RetrievalCase] = []
    seen_case_ids: set[str] = set()
    file_path = Path(path)

    with file_path.open("r", encoding="utf-8-sig") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue

            record = json.loads(line)
            top_level = _ensure_object(record, f"line {line_number}")
            missing_fields = [field for field in _TOP_LEVEL_FIELDS if field not in top_level]
            if missing_fields:
                raise ValueError(f"line {line_number} missing required fields: {', '.join(missing_fields)}")

            case_id = _ensure_string(top_level["case_id"], f"line {line_number} case_id")
            if case_id in seen_case_ids:
                raise ValueError(f"line {line_number} case_id must be unique: {case_id}")
            seen_case_ids.add(case_id)

            query = _ensure_string(top_level["query"], f"line {line_number} query")
            source_type = _ensure_source_type(top_level["source_type"], f"line {line_number} source_type")
            expected_chunk_ids = _ensure_expected_chunk_ids(
                top_level["expected_chunk_ids"],
                f"line {line_number} expected_chunk_ids",
            )
            query_origin = _ensure_choice(
                top_level.get("query_origin", "light_rewrite"),
                f"line {line_number} query_origin",
                _ALLOWED_QUERY_ORIGINS,
            )
            case_type = _ensure_choice(
                top_level.get(
                    "case_type",
                    "product_hard" if source_type == "product" else "playbook_hard",
                ),
                f"line {line_number} case_type",
                _ALLOWED_CASE_TYPES,
            )
            source_uid = _ensure_string(top_level.get("source_uid", case_id), f"line {line_number} source_uid")
            acceptable_chunk_ids = _ensure_expected_chunk_ids(
                top_level.get("acceptable_chunk_ids", expected_chunk_ids),
                f"line {line_number} acceptable_chunk_ids",
            )

            notes = top_level.get("notes", "")
            if notes == "":
                normalized_notes = ""
            else:
                normalized_notes = _ensure_string(notes, f"line {line_number} notes")

            cases.append(
                cast(
                    RetrievalCase,
                    {
                        "case_id": case_id,
                        "query": query,
                        "source_type": source_type,
                        "query_origin": query_origin,
                        "case_type": case_type,
                        "source_uid": source_uid,
                        "expected_chunk_ids": expected_chunk_ids,
                        "acceptable_chunk_ids": acceptable_chunk_ids,
                        "notes": normalized_notes,
                    },
                )
            )

    return cases


def _keyword_only_retrieve(db_path, *, source_type: str, query: str, top_k: int = _DEFAULT_TOP_K) -> list[dict]:
    storage_source_type = None if source_type == "mixed" else source_type
    rows = storage.list_knowledge_chunks(db_path, source_type=storage_source_type)
    return keyword_retrieve(query, rows, top_k=top_k)


def _mode_metrics(expected_chunk_ids: list[int], ranked_chunk_ids: list[int]) -> RetrievalModeResult:
    return cast(
        RetrievalModeResult,
        {
            "ranked_chunk_ids": ranked_chunk_ids,
            "recall_at_1": recall_at_k(expected_chunk_ids, ranked_chunk_ids, 1),
            "recall_at_3": recall_at_k(expected_chunk_ids, ranked_chunk_ids, 3),
            "recall_at_5": recall_at_k(expected_chunk_ids, ranked_chunk_ids, 5),
            "mrr": reciprocal_rank(expected_chunk_ids, ranked_chunk_ids),
        },
    )


def _ranked_chunk_ids(rows: list[dict]) -> list[int]:
    return [int(row["id"]) for row in rows if "id" in row]


def run_retrieval_benchmark(
    *,
    cases_path: str | Path,
    db_path,
    top_k: int = _DEFAULT_TOP_K,
    embedder: object = _USE_DEFAULT_EMBEDDER,
    reranker: object | None = None,
) -> dict:
    cases = load_retrieval_cases(cases_path)

    rows_by_mode: dict[str, list[dict[str, object]]] = {"keyword_only": [], "hybrid": [], "hybrid_rerank": []}
    case_results: list[RetrievalCaseResult] = []

    for case in cases:
        keyword_rows = _keyword_only_retrieve(
            db_path,
            source_type=case["source_type"],
            query=case["query"],
            top_k=top_k,
        )
        hybrid_kwargs = {
            "source_type": case["source_type"],
            "query": case["query"],
            "top_k": top_k,
        }
        if embedder is not _USE_DEFAULT_EMBEDDER:
            hybrid_kwargs["embedder"] = embedder

        hybrid_rows = hybrid_retrieve_knowledge_chunks(db_path, **hybrid_kwargs)
        hybrid_rerank_kwargs = dict(hybrid_kwargs)
        hybrid_rerank_kwargs["reranker"] = reranker
        hybrid_rerank_rows = hybrid_rerank_knowledge_chunks(db_path, **hybrid_rerank_kwargs)

        keyword_ranked_ids = _ranked_chunk_ids(keyword_rows)
        hybrid_ranked_ids = _ranked_chunk_ids(hybrid_rows)
        hybrid_rerank_ranked_ids = _ranked_chunk_ids(hybrid_rerank_rows)

        keyword_metrics = _mode_metrics(case["expected_chunk_ids"], keyword_ranked_ids)
        hybrid_metrics = _mode_metrics(case["expected_chunk_ids"], hybrid_ranked_ids)
        hybrid_rerank_metrics = _mode_metrics(case["expected_chunk_ids"], hybrid_rerank_ranked_ids)

        rows_by_mode["keyword_only"].append(
            {
                "case_id": case["case_id"],
                "case_type": case["case_type"],
                **keyword_metrics,
            }
        )
        rows_by_mode["hybrid"].append(
            {
                "case_id": case["case_id"],
                "case_type": case["case_type"],
                **hybrid_metrics,
            }
        )
        rows_by_mode["hybrid_rerank"].append(
            {
                "case_id": case["case_id"],
                "case_type": case["case_type"],
                **hybrid_rerank_metrics,
            }
        )

        case_results.append(
            cast(
                RetrievalCaseResult,
                {
                    "case_id": case["case_id"],
                    "query": case["query"],
                    "source_type": case["source_type"],
                    "query_origin": case["query_origin"],
                    "case_type": case["case_type"],
                    "source_uid": case["source_uid"],
                    "expected_chunk_ids": case["expected_chunk_ids"],
                    "acceptable_chunk_ids": case["acceptable_chunk_ids"],
                    "notes": case["notes"],
                    "modes": {
                        "keyword_only": keyword_metrics,
                        "hybrid": hybrid_metrics,
                        "hybrid_rerank": hybrid_rerank_metrics,
                    },
                },
            )
        )

    summary = summarize_retrieval_metrics(rows_by_mode)
    bucket_summary = summarize_retrieval_metrics_by_bucket(rows_by_mode)
    return {
        "summary": summary,
        "bucket_summary": bucket_summary,
        "case_results": case_results,
    }
