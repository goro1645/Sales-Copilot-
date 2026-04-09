from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol


logger = logging.getLogger(__name__)


class Reranker(Protocol):
    model_name: str

    def score_pairs(self, pairs: list[tuple[str, str]]) -> list[float]:
        ...


@dataclass
class FakeReranker:
    mapping: dict[tuple[str, str], float]
    model_name: str = "fake-reranker"

    def score_pairs(self, pairs: list[tuple[str, str]]) -> list[float]:
        return [float(self.mapping[pair]) for pair in pairs]


class CrossEncoderReranker:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        from sentence_transformers import CrossEncoder

        self._model = CrossEncoder(model_name)

    def score_pairs(self, pairs: list[tuple[str, str]]) -> list[float]:
        if not pairs:
            return []
        scores = self._model.predict(pairs)
        return [float(score) for score in scores]


@lru_cache(maxsize=2)
def load_default_reranker() -> CrossEncoderReranker | None:
    try:
        return CrossEncoderReranker()
    except Exception as exc:  # pragma: no cover - depends on local model availability
        logger.warning("Falling back to hybrid-only retrieval because reranker failed to load: %s", exc)
        return None
