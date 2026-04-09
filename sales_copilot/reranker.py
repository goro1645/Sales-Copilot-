from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol


logger = logging.getLogger(__name__)
DEFAULT_RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
RERANKER_MODEL_ENV_VAR = "SALES_COPILOT_RERANKER_MODEL"


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
    def __init__(self, model_name: str = DEFAULT_RERANKER_MODEL):
        self.model_name = model_name
        from sentence_transformers import CrossEncoder

        self._model = CrossEncoder(model_name)

    def score_pairs(self, pairs: list[tuple[str, str]]) -> list[float]:
        if not pairs:
            return []
        scores = self._model.predict(pairs)
        return [float(score) for score in scores]


def get_default_reranker_model_name() -> str:
    return os.getenv(RERANKER_MODEL_ENV_VAR, "").strip() or DEFAULT_RERANKER_MODEL


@lru_cache(maxsize=4)
def _load_reranker_for_model(model_name: str) -> CrossEncoderReranker | None:
    try:
        return CrossEncoderReranker(model_name=model_name)
    except Exception as exc:  # pragma: no cover - depends on local model availability
        logger.warning("Falling back to hybrid-only retrieval because reranker failed to load: %s", exc)
        return None


def load_default_reranker(model_name: str | None = None) -> CrossEncoderReranker | None:
    return _load_reranker_for_model(model_name or get_default_reranker_model_name())
