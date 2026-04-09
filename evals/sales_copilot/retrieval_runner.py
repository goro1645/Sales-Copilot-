from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict, cast

from evals.sales_copilot.csds_adapter import load_full_csds_cases
from evals.sales_copilot.csds_runner import _run_parse_step
from evals.sales_copilot.dual_path_query_builder import build_retrieval_query
from evals.sales_copilot.retrieval_metrics import (
    recall_at_k,
    reciprocal_rank,
    summarize_dual_path_gap,
    summarize_dual_path_gap_by_bucket,
    summarize_retrieval_metrics_by_bucket,
    summarize_retrieval_metrics,
)
from sales_copilot import storage
from sales_copilot.retrieval import (
    hybrid_retrieve_knowledge_chunks,
    hybrid_rerank_knowledge_chunks,
    rerank_only_knowledge_chunks,
)
from sales_copilot.tools import keyword_retrieve


class StructuredParsePayload(TypedDict):
    confirmed_needs: list[str]
    next_steps: list[str]
    timeline_signals: list[str]
    risk_flags: list[str]


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
    gold_parse: StructuredParsePayload
    source_split: str
    customer_profile_text: str
    meeting_note_text: str


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


class DualPathSideResult(TypedDict):
    query: str
    modes: dict[str, RetrievalModeResult]
    parse_payload: dict[str, Any]
    errors: list[str]


class DualPathCaseResult(TypedDict):
    case_id: str
    source_type: str
    query_origin: str
    case_type: str
    source_uid: str
    expected_chunk_ids: list[int]
    acceptable_chunk_ids: list[int]
    notes: str
    gold: DualPathSideResult
    model: DualPathSideResult


_DEFAULT_TOP_K = 5
_TOP_LEVEL_FIELDS = ("case_id", "query", "source_type", "expected_chunk_ids")
_ALLOWED_SOURCE_TYPES = {"product", "playbook", "mixed"}
_ALLOWED_QUERY_ORIGINS = {"raw_user_phrase", "light_rewrite"}
_ALLOWED_CASE_TYPES = {"product_hard", "playbook_hard", "cross_source_confusing"}
_USE_DEFAULT_EMBEDDER = object()
_DEFAULT_GOLD_PARSE_BY_CHUNK: dict[int, StructuredParsePayload] = {
    1: {
        "confirmed_needs": ["account memory", "readable history"],
        "next_steps": ["tracked follow-up actions"],
        "timeline_signals": [],
        "risk_flags": [],
    },
    2: {
        "confirmed_needs": ["deployment model", "audit trail"],
        "next_steps": [],
        "timeline_signals": [],
        "risk_flags": ["security_review"],
    },
    3: {
        "confirmed_needs": ["crm write-back", "stage updates"],
        "next_steps": ["keep next-step notes consistent"],
        "timeline_signals": [],
        "risk_flags": [],
    },
    4: {
        "confirmed_needs": ["top pain points", "current workflow"],
        "next_steps": ["identify decision owner"],
        "timeline_signals": [],
        "risk_flags": [],
    },
    5: {
        "confirmed_needs": ["security concerns"],
        "next_steps": ["send security checklist", "schedule technical demo"],
        "timeline_signals": [],
        "risk_flags": ["security_review"],
    },
    6: {
        "confirmed_needs": ["clear next step"],
        "next_steps": ["assign one owner", "set one due date"],
        "timeline_signals": [],
        "risk_flags": [],
    },
}


def _ensure_object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _ensure_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def _ensure_optional_string(value: object, label: str) -> str:
    if value in (None, ""):
        return ""
    return _ensure_string(value, label)


def _ensure_string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list of strings")
    normalized: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{label}[{index}] must be a non-empty string")
        normalized.append(item.strip())
    return normalized


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


def _normalize_parse_payload(payload: dict[str, object], *, label: str) -> StructuredParsePayload:
    return cast(
        StructuredParsePayload,
        {
            "confirmed_needs": _ensure_string_list(payload.get("confirmed_needs", []), f"{label}.confirmed_needs"),
            "next_steps": _ensure_string_list(payload.get("next_steps", []), f"{label}.next_steps"),
            "timeline_signals": _ensure_string_list(payload.get("timeline_signals", []), f"{label}.timeline_signals"),
            "risk_flags": _ensure_string_list(payload.get("risk_flags", []), f"{label}.risk_flags"),
        },
    )


def _default_gold_parse(case_id: str, *, expected_chunk_ids: list[int], query: str) -> StructuredParsePayload:
    primary_chunk = expected_chunk_ids[0]
    payload = dict(_DEFAULT_GOLD_PARSE_BY_CHUNK.get(primary_chunk, _DEFAULT_GOLD_PARSE_BY_CHUNK[1]))
    lowered_query = query.lower()
    if "sso" in lowered_query and "sso" not in " ".join(payload["confirmed_needs"]).lower():
        payload["confirmed_needs"] = [*payload["confirmed_needs"], "sso support"]
    if "data isolation" in lowered_query and "data isolation" not in " ".join(payload["confirmed_needs"]).lower():
        payload["confirmed_needs"] = [*payload["confirmed_needs"], "data isolation"]
    if "checklist" in lowered_query and "send security checklist" not in payload["next_steps"]:
        payload["next_steps"] = [*payload["next_steps"], "send security checklist"]
    if "demo" in lowered_query and "schedule technical demo" not in payload["next_steps"]:
        payload["next_steps"] = [*payload["next_steps"], "schedule technical demo"]
    if "owner" in lowered_query and "assign one owner" not in payload["next_steps"]:
        payload["next_steps"] = [*payload["next_steps"], "assign one owner"]
    if "due date" in lowered_query and "set one due date" not in payload["next_steps"]:
        payload["next_steps"] = [*payload["next_steps"], "set one due date"]
    if case_id.startswith("csds_cross_") and primary_chunk in {2, 5} and "security_review" not in payload["risk_flags"]:
        payload["risk_flags"] = [*payload["risk_flags"], "security_review"]
    return cast(StructuredParsePayload, payload)


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
            normalized_notes = "" if notes == "" else _ensure_string(notes, f"line {line_number} notes")

            gold_parse_value = top_level.get("gold_parse")
            if gold_parse_value is None:
                gold_parse = _default_gold_parse(case_id, expected_chunk_ids=expected_chunk_ids, query=query)
            else:
                gold_parse = _normalize_parse_payload(
                    _ensure_object(gold_parse_value, f"line {line_number} gold_parse"),
                    label=f"line {line_number} gold_parse",
                )

            source_split_value = top_level.get("source_split", "")
            if source_split_value == "":
                source_split = ""
            else:
                source_split = _ensure_string(source_split_value, f"line {line_number} source_split")

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
                        "gold_parse": gold_parse,
                        "source_split": source_split,
                        "customer_profile_text": _ensure_optional_string(
                            top_level.get("customer_profile_text", ""),
                            f"line {line_number} customer_profile_text",
                        ),
                        "meeting_note_text": _ensure_optional_string(
                            top_level.get("meeting_note_text", ""),
                            f"line {line_number} meeting_note_text",
                        ),
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


def _evaluate_query_modes(
    *,
    db_path,
    case: RetrievalCase,
    query: str,
    top_k: int,
    embedder: object,
    reranker: object | None,
) -> dict[str, RetrievalModeResult]:
    if not query:
        empty_metrics = _mode_metrics(case["expected_chunk_ids"], [])
        return {
            "keyword_only": empty_metrics,
            "hybrid": empty_metrics,
            "hybrid_rerank": empty_metrics,
            "rerank_only": empty_metrics,
        }

    keyword_rows = _keyword_only_retrieve(
        db_path,
        source_type=case["source_type"],
        query=query,
        top_k=top_k,
    )
    hybrid_kwargs = {
        "source_type": case["source_type"],
        "query": query,
        "top_k": top_k,
    }
    if embedder is not _USE_DEFAULT_EMBEDDER:
        hybrid_kwargs["embedder"] = embedder

    hybrid_rows = hybrid_retrieve_knowledge_chunks(db_path, **hybrid_kwargs)
    hybrid_rerank_kwargs = dict(hybrid_kwargs)
    hybrid_rerank_kwargs["reranker"] = reranker
    hybrid_rerank_rows = hybrid_rerank_knowledge_chunks(db_path, **hybrid_rerank_kwargs)
    rerank_only_kwargs = dict(hybrid_kwargs)
    rerank_only_kwargs["reranker"] = reranker
    rerank_only_rows = rerank_only_knowledge_chunks(db_path, **rerank_only_kwargs)

    keyword_ranked_ids = _ranked_chunk_ids(keyword_rows)
    hybrid_ranked_ids = _ranked_chunk_ids(hybrid_rows)
    hybrid_rerank_ranked_ids = _ranked_chunk_ids(hybrid_rerank_rows)
    rerank_only_ranked_ids = _ranked_chunk_ids(rerank_only_rows)
    return {
        "keyword_only": _mode_metrics(case["expected_chunk_ids"], keyword_ranked_ids),
        "hybrid": _mode_metrics(case["expected_chunk_ids"], hybrid_ranked_ids),
        "hybrid_rerank": _mode_metrics(case["expected_chunk_ids"], hybrid_rerank_ranked_ids),
        "rerank_only": _mode_metrics(case["expected_chunk_ids"], rerank_only_ranked_ids),
    }


def run_retrieval_benchmark(
    *,
    cases_path: str | Path,
    db_path,
    top_k: int = _DEFAULT_TOP_K,
    embedder: object = _USE_DEFAULT_EMBEDDER,
    reranker: object | None = None,
) -> dict:
    cases = load_retrieval_cases(cases_path)

    rows_by_mode: dict[str, list[dict[str, object]]] = _rows_by_mode_template()
    case_results: list[RetrievalCaseResult] = []

    for case in cases:
        mode_results = _evaluate_query_modes(
            db_path=db_path,
            case=case,
            query=case["query"],
            top_k=top_k,
            embedder=embedder,
            reranker=reranker,
        )

        for mode, metrics in mode_results.items():
            rows_by_mode[mode].append(
                {
                    "case_id": case["case_id"],
                    "case_type": case["case_type"],
                    **metrics,
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
                    "modes": mode_results,
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


def _load_csds_case_lookup(dataset_dir: str | Path) -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    for case in load_full_csds_cases(Path(dataset_dir)):
        source_uid = str(case["source_uid"])
        if source_uid in lookup:
            continue
        lookup[source_uid] = {
            "customer_profile_text": case["customer_profile_text"],
            "meeting_note_text": case["meeting_note_text"],
        }
    return lookup


def _resolve_model_inputs(
    case: RetrievalCase,
    *,
    csds_lookup: dict[str, dict[str, str]] | None,
) -> tuple[str, str]:
    customer_profile_text = case.get("customer_profile_text", "")
    meeting_note_text = case.get("meeting_note_text", "")
    if customer_profile_text and meeting_note_text:
        return customer_profile_text, meeting_note_text

    if csds_lookup is None:
        raise ValueError("dual-path retrieval requires customer_profile_text/meeting_note_text or csds_data_dir")

    source_case = csds_lookup.get(case["source_uid"])
    if source_case is None:
        raise ValueError(f"missing CSDS source case for source_uid={case['source_uid']}")
    return source_case["customer_profile_text"], source_case["meeting_note_text"]


def _run_model_parse_for_case(
    case: RetrievalCase,
    *,
    llm_client,
    csds_lookup: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    customer_profile_text, meeting_note_text = _resolve_model_inputs(case, csds_lookup=csds_lookup)
    parse_payload = _run_parse_step(
        {
            "customer_profile_text": customer_profile_text,
            "meeting_note_text": meeting_note_text,
        },
        llm_client=llm_client,
    )
    if not isinstance(parse_payload, dict):
        return {}
    return parse_payload


def _rows_by_mode_template() -> dict[str, list[dict[str, object]]]:
    return {"keyword_only": [], "hybrid": [], "hybrid_rerank": [], "rerank_only": []}


def run_dual_path_retrieval_benchmark(
    *,
    cases_path: str | Path,
    db_path,
    llm_client,
    csds_data_dir: str | Path | None = None,
    top_k: int = _DEFAULT_TOP_K,
    embedder: object = _USE_DEFAULT_EMBEDDER,
    reranker: object | None = None,
) -> dict[str, Any]:
    cases = load_retrieval_cases(cases_path)
    csds_lookup = _load_csds_case_lookup(csds_data_dir) if csds_data_dir else None

    rows_by_path = {"gold": _rows_by_mode_template(), "model": _rows_by_mode_template()}
    case_results: list[DualPathCaseResult] = []

    for case in cases:
        gold_query = build_retrieval_query(case["gold_parse"])
        gold_modes = _evaluate_query_modes(
            db_path=db_path,
            case=case,
            query=gold_query,
            top_k=top_k,
            embedder=embedder,
            reranker=reranker,
        )

        model_errors: list[str] = []
        model_parse: dict[str, Any] = {}
        try:
            model_parse = _run_model_parse_for_case(case, llm_client=llm_client, csds_lookup=csds_lookup)
        except Exception as exc:
            model_errors.append(f"parse error: {exc}")
        model_query = build_retrieval_query(model_parse) if model_parse else ""
        model_modes = _evaluate_query_modes(
            db_path=db_path,
            case=case,
            query=model_query,
            top_k=top_k,
            embedder=embedder,
            reranker=reranker,
        )

        for mode, metrics in gold_modes.items():
            rows_by_path["gold"][mode].append(
                {
                    "case_id": case["case_id"],
                    "case_type": case["case_type"],
                    **metrics,
                }
            )
        for mode, metrics in model_modes.items():
            rows_by_path["model"][mode].append(
                {
                    "case_id": case["case_id"],
                    "case_type": case["case_type"],
                    **metrics,
                }
            )

        case_results.append(
            cast(
                DualPathCaseResult,
                {
                    "case_id": case["case_id"],
                    "source_type": case["source_type"],
                    "query_origin": case["query_origin"],
                    "case_type": case["case_type"],
                    "source_uid": case["source_uid"],
                    "expected_chunk_ids": case["expected_chunk_ids"],
                    "acceptable_chunk_ids": case["acceptable_chunk_ids"],
                    "notes": case["notes"],
                    "gold": {
                        "query": gold_query,
                        "parse_payload": case["gold_parse"],
                        "modes": gold_modes,
                        "errors": [],
                    },
                    "model": {
                        "query": model_query,
                        "parse_payload": model_parse,
                        "modes": model_modes,
                        "errors": model_errors,
                    },
                },
            )
        )

    summary_by_path = {
        path: summarize_retrieval_metrics(rows_by_mode) for path, rows_by_mode in rows_by_path.items()
    }
    bucket_summary_by_path = {
        path: summarize_retrieval_metrics_by_bucket(rows_by_mode) for path, rows_by_mode in rows_by_path.items()
    }
    return {
        "report_kind": "dual_path",
        "summary": summary_by_path,
        "bucket_summary": bucket_summary_by_path,
        "gap": {
            "overall": summarize_dual_path_gap(summary_by_path),
            "bucket_summary": summarize_dual_path_gap_by_bucket(bucket_summary_by_path),
        },
        "case_results": case_results,
    }
