from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from math import sqrt
from typing import Protocol

import numpy as np

from sales_copilot.reranker import Reranker, load_default_reranker
from sales_copilot import storage
from sales_copilot.tools import keyword_retrieve


logger = logging.getLogger(__name__)
_USE_DEFAULT_EMBEDDER = object()
_USE_DEFAULT_RERANKER = object()


class Embedder(Protocol):
    model_name: str

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...


@dataclass
class FakeEmbedder:
    mapping: dict[str, list[float]]
    model_name: str = "fake-model"

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self.mapping[text] for text in texts]


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):
        self.model_name = model_name
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return [np.asarray(vector, dtype=float).tolist() for vector in vectors]


@lru_cache(maxsize=2)
def load_default_embedder() -> SentenceTransformerEmbedder | None:
    try:
        return SentenceTransformerEmbedder()
    except Exception as exc:  # pragma: no cover - depends on local model availability
        logger.warning("Falling back to keyword retrieval because embedding model failed to load: %s", exc)
        return None


def cosine_similarity(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = sqrt(sum(a * a for a in left))
    right_norm = sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def _normalize_keyword_scores(rows: list[dict]) -> dict[int, float]:
    if not rows:
        return {}
    max_score = max(float(row.get("score", 0.0)) for row in rows) or 1.0
    return {int(row["id"]): float(row.get("score", 0.0)) / max_score for row in rows if "id" in row}


def _normalize_dense_scores(scores: list[float]) -> list[float]:
    if not scores:
        return []
    min_score = min(scores)
    max_score = max(scores)
    if max_score == min_score:
        return [1.0 for _ in scores]
    scale = max_score - min_score
    return [(score - min_score) / scale for score in scores]


def hybrid_retrieve_rows(query: str, rows: list[dict], *, embedder: Embedder | None, top_k: int = 3) -> list[dict]:
    keyword_rows = keyword_retrieve(query, rows, top_k=max(top_k, len(rows)))
    keyword_score_map = _normalize_keyword_scores(keyword_rows)

    if embedder is None:
        return [
            {
                **row,
                "keyword_score": keyword_score_map.get(int(row["id"]), 0.0),
                "vector_score": 0.0,
                "hybrid_score": keyword_score_map.get(int(row["id"]), 0.0),
                "retrieval_mode": "keyword_only",
            }
            for row in keyword_rows[:top_k]
        ]

    texts = [query] + [str(row.get("chunk_text", "")) for row in rows]
    vectors = embedder.embed_texts(texts)
    query_vector = vectors[0]
    chunk_vectors = vectors[1:]

    ranked = []
    for row, vector in zip(rows, chunk_vectors):
        keyword_score = keyword_score_map.get(int(row.get("id", -1)), 0.0)
        vector_score = cosine_similarity(query_vector, vector)
        hybrid_score = 0.7 * vector_score + 0.3 * keyword_score
        ranked.append(
            {
                **row,
                "keyword_score": keyword_score,
                "vector_score": vector_score,
                "hybrid_score": hybrid_score,
                "retrieval_mode": "hybrid",
                "matched_terms": row.get("matched_terms", []),
            }
        )
    ranked.sort(key=lambda item: item["hybrid_score"], reverse=True)
    return ranked[:top_k]


def hybrid_rerank_retrieve_rows(
    query: str,
    rows: list[dict],
    *,
    embedder: Embedder | None,
    reranker: Reranker | None,
    top_k: int = 3,
    rerank_candidate_k: int = 10,
) -> list[dict]:
    candidate_k = min(len(rows), max(top_k, rerank_candidate_k))
    hybrid_rows = hybrid_retrieve_rows(query, rows, embedder=embedder, top_k=candidate_k)

    if reranker is None:
        return hybrid_rows[:top_k]

    pairs = [(query, str(row.get("chunk_text", ""))) for row in hybrid_rows]
    rerank_scores_raw = [float(score) for score in reranker.score_pairs(pairs)]
    rerank_scores = _normalize_dense_scores(rerank_scores_raw)

    reranked: list[dict] = []
    for row, rerank_score_raw, rerank_score in zip(hybrid_rows, rerank_scores_raw, rerank_scores):
        hybrid_score = float(row.get("hybrid_score", 0.0))
        final_score = 0.7 * float(rerank_score) + 0.3 * hybrid_score
        reranked.append(
            {
                **row,
                "rerank_score_raw": float(rerank_score_raw),
                "rerank_score": float(rerank_score),
                "final_score": final_score,
                "retrieval_mode": "hybrid_rerank",
            }
        )

    reranked.sort(key=lambda item: (item["final_score"], item.get("hybrid_score", 0.0)), reverse=True)
    return reranked[:top_k]


def rerank_only_retrieve_rows(
    query: str,
    rows: list[dict],
    *,
    embedder: Embedder | None,
    reranker: Reranker | None,
    top_k: int = 3,
    rerank_candidate_k: int = 10,
) -> list[dict]:
    candidate_k = min(len(rows), max(top_k, rerank_candidate_k))
    hybrid_rows = hybrid_retrieve_rows(query, rows, embedder=embedder, top_k=candidate_k)

    if reranker is None:
        return hybrid_rows[:top_k]

    pairs = [(query, str(row.get("chunk_text", ""))) for row in hybrid_rows]
    rerank_scores_raw = [float(score) for score in reranker.score_pairs(pairs)]
    rerank_scores = _normalize_dense_scores(rerank_scores_raw)

    reranked: list[dict] = []
    for row, rerank_score_raw, rerank_score in zip(hybrid_rows, rerank_scores_raw, rerank_scores):
        reranked.append(
            {
                **row,
                "rerank_score_raw": float(rerank_score_raw),
                "rerank_score": float(rerank_score),
                "retrieval_mode": "rerank_only",
            }
        )

    reranked.sort(key=lambda item: (item["rerank_score"], item.get("hybrid_score", 0.0)), reverse=True)
    return reranked[:top_k]


def hybrid_retrieve_knowledge_chunks(
    db_path,
    *,
    source_type: str | None,
    query: str,
    embedder: Embedder | None | object = _USE_DEFAULT_EMBEDDER,
    top_k: int = 3,
) -> list[dict]:
    storage_source_type = None if source_type in (None, "mixed") else source_type
    rows = storage.list_knowledge_chunks(db_path, source_type=storage_source_type)
    active_embedder = load_default_embedder() if embedder is _USE_DEFAULT_EMBEDDER else embedder
    if active_embedder is None:
        return hybrid_retrieve_rows(query, rows, embedder=None, top_k=top_k)

    query_vector = active_embedder.embed_texts([query])[0]
    keyword_rows = keyword_retrieve(query, rows, top_k=max(top_k, len(rows)))
    keyword_score_map = _normalize_keyword_scores(keyword_rows)

    ranked: list[dict] = []
    for row in rows:
        cached = storage.get_knowledge_chunk_embedding(
            db_path,
            chunk_id=int(row["id"]),
            model_name=active_embedder.model_name,
        )
        if cached is None:
            chunk_vector = active_embedder.embed_texts([str(row.get("chunk_text", ""))])[0]
            storage.upsert_knowledge_chunk_embedding(
                db_path,
                chunk_id=int(row["id"]),
                model_name=active_embedder.model_name,
                embedding=chunk_vector,
            )
        else:
            chunk_vector = cached["embedding"]

        keyword_score = keyword_score_map.get(int(row["id"]), 0.0)
        vector_score = cosine_similarity(query_vector, chunk_vector)
        hybrid_score = 0.7 * vector_score + 0.3 * keyword_score
        ranked.append(
            {
                **row,
                "keyword_score": keyword_score,
                "vector_score": vector_score,
                "hybrid_score": hybrid_score,
                "retrieval_mode": "hybrid",
            }
        )

    ranked.sort(key=lambda item: item["hybrid_score"], reverse=True)
    return ranked[:top_k]


def hybrid_rerank_knowledge_chunks(
    db_path,
    *,
    source_type: str | None,
    query: str,
    embedder: Embedder | None | object = _USE_DEFAULT_EMBEDDER,
    reranker: Reranker | None | object = _USE_DEFAULT_RERANKER,
    top_k: int = 3,
    rerank_candidate_k: int = 10,
) -> list[dict]:
    storage_source_type = None if source_type in (None, "mixed") else source_type
    rows = storage.list_knowledge_chunks(db_path, source_type=storage_source_type)
    active_embedder = load_default_embedder() if embedder is _USE_DEFAULT_EMBEDDER else embedder
    active_reranker = load_default_reranker() if reranker is _USE_DEFAULT_RERANKER else reranker
    return hybrid_rerank_retrieve_rows(
        query,
        rows,
        embedder=active_embedder,
        reranker=active_reranker,
        top_k=top_k,
        rerank_candidate_k=rerank_candidate_k,
    )


def rerank_only_knowledge_chunks(
    db_path,
    *,
    source_type: str | None,
    query: str,
    embedder: Embedder | None | object = _USE_DEFAULT_EMBEDDER,
    reranker: Reranker | None | object = _USE_DEFAULT_RERANKER,
    top_k: int = 3,
    rerank_candidate_k: int = 10,
) -> list[dict]:
    storage_source_type = None if source_type in (None, "mixed") else source_type
    rows = storage.list_knowledge_chunks(db_path, source_type=storage_source_type)
    active_embedder = load_default_embedder() if embedder is _USE_DEFAULT_EMBEDDER else embedder
    active_reranker = load_default_reranker() if reranker is _USE_DEFAULT_RERANKER else reranker
    return rerank_only_retrieve_rows(
        query,
        rows,
        embedder=active_embedder,
        reranker=active_reranker,
        top_k=top_k,
        rerank_candidate_k=rerank_candidate_k,
    )
