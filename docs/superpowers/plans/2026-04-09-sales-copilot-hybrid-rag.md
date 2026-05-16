I'm using the writing-plans skill to create the implementation plan.

# Sales Copilot Hybrid Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade Sales Copilot from keyword-only retrieval to hybrid retrieval with vector similarity plus keyword fallback.

**Architecture:** Add a focused retrieval module that owns embeddings, cache reads/writes, and hybrid ranking. Keep SQLite as the only persistence layer, integrate retrieval through the existing workflow node, and preserve keyword-only fallback whenever embeddings are unavailable.

**Tech Stack:** Python, SQLite, sentence-transformers, NumPy, LangGraph, pytest

---

## File Map

- Create: `sales_copilot/retrieval.py`
  - Embedding provider interface, SQLite embedding cache, cosine similarity, hybrid ranking, product/playbook retrieval helpers.
- Create: `scripts/rebuild_sales_copilot_embeddings.py`
  - CLI script to precompute and store embeddings for knowledge chunks.
- Modify: `sales_copilot/storage.py`
  - Add `knowledge_chunk_embeddings` table plus cache CRUD helpers.
- Modify: `sales_copilot/tools.py`
  - Keep keyword retrieval, expose it for hybrid retrieval reuse, and route knowledge search through retrieval helpers when requested.
- Modify: `sales_copilot/graph.py`
  - Switch `retrieve_context_node()` to hybrid retrieval while keeping account history unchanged.
- Test: `tests/sales_copilot/test_retrieval.py`
  - Unit tests for fake embedder, hybrid ranking, cache, fallback.
- Test: `tests/sales_copilot/test_graph.py`
  - Retrieval node integration coverage.
- Test: `tests/scripts/test_rebuild_sales_copilot_embeddings.py`
  - CLI indexing behavior.
- Modify: `README.md`
  - Document hybrid retrieval and embedding rebuild command.

### Task 1: Add embedding cache support to storage

**Files:**
- Modify: `D:/minimind/.worktrees/minimind-job-agent/sales_copilot/storage.py`
- Test: `D:/minimind/.worktrees/minimind-job-agent/tests/sales_copilot/test_retrieval.py`

- [ ] **Step 1: Write the failing storage cache test**

```python
def test_upsert_and_get_knowledge_chunk_embedding(tmp_path):
    from sales_copilot import storage

    db_path = tmp_path / "sales.db"
    storage.init_storage(db_path)
    chunk_id = storage.save_knowledge_chunk(
        db_path,
        {
            "source_type": "product",
            "source_name": "Demo Product",
            "chunk_text": "Private deployment and audit logging.",
            "tags_json": '["deployment"]',
            "retrieval_metadata_json": '{}',
        },
    )

    storage.upsert_knowledge_chunk_embedding(
        db_path,
        chunk_id=chunk_id,
        model_name="fake-model",
        embedding=[0.1, 0.2, 0.3],
    )

    row = storage.get_knowledge_chunk_embedding(db_path, chunk_id=chunk_id, model_name="fake-model")

    assert row is not None
    assert row["chunk_id"] == chunk_id
    assert row["model_name"] == "fake-model"
    assert row["embedding"] == [0.1, 0.2, 0.3]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest D:/minimind/.worktrees/minimind-job-agent/tests/sales_copilot/test_retrieval.py::test_upsert_and_get_knowledge_chunk_embedding -v`
Expected: FAIL with missing storage helpers or schema.

- [ ] **Step 3: Write minimal storage implementation**

Add to `storage.py`:

```python
import json
```

Extend `init_storage()` schema script with:

```sql
CREATE TABLE IF NOT EXISTS knowledge_chunk_embeddings (
    chunk_id INTEGER NOT NULL REFERENCES knowledge_chunks(id) ON DELETE CASCADE,
    model_name TEXT NOT NULL,
    embedding_json TEXT NOT NULL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (chunk_id, model_name)
);
```

Add helpers:

```python
def save_knowledge_chunk(db_path, record: dict) -> int:
    init_storage(db_path)
    with _connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO knowledge_chunks (source_type, source_name, chunk_text, tags_json, retrieval_metadata_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                record["source_type"],
                record["source_name"],
                record["chunk_text"],
                record["tags_json"],
                record["retrieval_metadata_json"],
            ),
        )
        conn.commit()
        return cursor.lastrowid


def upsert_knowledge_chunk_embedding(db_path, *, chunk_id: int, model_name: str, embedding: list[float]) -> None:
    init_storage(db_path)
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO knowledge_chunk_embeddings (chunk_id, model_name, embedding_json, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(chunk_id, model_name)
            DO UPDATE SET embedding_json = excluded.embedding_json, updated_at = CURRENT_TIMESTAMP
            """,
            (chunk_id, model_name, json.dumps(embedding)),
        )
        conn.commit()


def get_knowledge_chunk_embedding(db_path, *, chunk_id: int, model_name: str) -> dict | None:
    init_storage(db_path)
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT chunk_id, model_name, embedding_json FROM knowledge_chunk_embeddings WHERE chunk_id = ? AND model_name = ?",
            (chunk_id, model_name),
        ).fetchone()
    if row is None:
        return None
    payload = dict(row)
    payload["embedding"] = json.loads(payload.pop("embedding_json"))
    return payload
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest D:/minimind/.worktrees/minimind-job-agent/tests/sales_copilot/test_retrieval.py::test_upsert_and_get_knowledge_chunk_embedding -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C D:/minimind/.worktrees/minimind-job-agent add sales_copilot/storage.py tests/sales_copilot/test_retrieval.py
git -C D:/minimind/.worktrees/minimind-job-agent commit -m "feat: add embedding cache storage"
```

### Task 2: Add retrieval module with fake embedder and hybrid ranking

**Files:**
- Create: `D:/minimind/.worktrees/minimind-job-agent/sales_copilot/retrieval.py`
- Modify: `D:/minimind/.worktrees/minimind-job-agent/sales_copilot/tools.py`
- Test: `D:/minimind/.worktrees/minimind-job-agent/tests/sales_copilot/test_retrieval.py`

- [ ] **Step 1: Write the failing retrieval tests**

```python
def test_hybrid_retrieve_prefers_vector_signal_when_available(tmp_path):
    from sales_copilot.retrieval import FakeEmbedder, hybrid_retrieve_rows

    rows = [
        {"id": 1, "chunk_text": "Private deployment with audit logging.", "source_name": "Doc A", "tags_json": "[]"},
        {"id": 2, "chunk_text": "Discount approval workflow.", "source_name": "Doc B", "tags_json": "[]"},
    ]
    embedder = FakeEmbedder(
        {
            "private deployment": [1.0, 0.0],
            "Private deployment with audit logging.": [1.0, 0.0],
            "Discount approval workflow.": [0.0, 1.0],
        }
    )

    results = hybrid_retrieve_rows("private deployment", rows, embedder=embedder, top_k=2)

    assert results[0]["source_name"] == "Doc A"
    assert results[0]["retrieval_mode"] == "hybrid"
    assert results[0]["vector_score"] > results[1]["vector_score"]


def test_hybrid_retrieve_falls_back_to_keyword_only_when_embedder_missing():
    from sales_copilot.retrieval import hybrid_retrieve_rows

    rows = [
        {"id": 1, "chunk_text": "CRM integration architecture.", "source_name": "Doc A", "tags_json": "[]"},
        {"id": 2, "chunk_text": "Discount approval workflow.", "source_name": "Doc B", "tags_json": "[]"},
    ]

    results = hybrid_retrieve_rows("CRM integration", rows, embedder=None, top_k=2)

    assert results[0]["source_name"] == "Doc A"
    assert all(item["retrieval_mode"] == "keyword_only" for item in results)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest D:/minimind/.worktrees/minimind-job-agent/tests/sales_copilot/test_retrieval.py::test_hybrid_retrieve_prefers_vector_signal_when_available D:/minimind/.worktrees/minimind-job-agent/tests/sales_copilot/test_retrieval.py::test_hybrid_retrieve_falls_back_to_keyword_only_when_embedder_missing -v`
Expected: FAIL because `retrieval.py` does not exist.

- [ ] **Step 3: Write minimal retrieval implementation**

Create `retrieval.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Protocol

from sales_copilot.tools import keyword_retrieve


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
        vector_score = cosine_similarity(query_vector, vector)
        keyword_score = keyword_score_map.get(int(row.get("id", -1)), 0.0)
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest D:/minimind/.worktrees/minimind-job-agent/tests/sales_copilot/test_retrieval.py::test_hybrid_retrieve_prefers_vector_signal_when_available D:/minimind/.worktrees/minimind-job-agent/tests/sales_copilot/test_retrieval.py::test_hybrid_retrieve_falls_back_to_keyword_only_when_embedder_missing -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C D:/minimind/.worktrees/minimind-job-agent add sales_copilot/retrieval.py sales_copilot/tools.py tests/sales_copilot/test_retrieval.py
git -C D:/minimind/.worktrees/minimind-job-agent commit -m "feat: add hybrid retrieval core"
```

### Task 3: Add production embedder and cache-backed retrieval helpers

**Files:**
- Modify: `D:/minimind/.worktrees/minimind-job-agent/sales_copilot/retrieval.py`
- Modify: `D:/minimind/.worktrees/minimind-job-agent/sales_copilot/storage.py`
- Test: `D:/minimind/.worktrees/minimind-job-agent/tests/sales_copilot/test_retrieval.py`

- [ ] **Step 1: Write failing cache-backed retrieval tests**

```python
def test_hybrid_retrieve_uses_cached_embeddings(tmp_path):
    from sales_copilot import storage
    from sales_copilot.retrieval import FakeEmbedder, hybrid_retrieve_knowledge_chunks

    db_path = tmp_path / "sales.db"
    storage.init_storage(db_path)
    chunk_id = storage.save_knowledge_chunk(
        db_path,
        {
            "source_type": "product",
            "source_name": "Doc A",
            "chunk_text": "Private deployment with audit logging.",
            "tags_json": "[]",
            "retrieval_metadata_json": "{}",
        },
    )
    storage.upsert_knowledge_chunk_embedding(db_path, chunk_id=chunk_id, model_name="fake-model", embedding=[1.0, 0.0])

    embedder = FakeEmbedder({"private deployment": [1.0, 0.0]})
    results = hybrid_retrieve_knowledge_chunks(db_path, source_type="product", query="private deployment", embedder=embedder, top_k=1)

    assert results[0]["id"] == chunk_id
    assert results[0]["retrieval_mode"] == "hybrid"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest D:/minimind/.worktrees/minimind-job-agent/tests/sales_copilot/test_retrieval.py::test_hybrid_retrieve_uses_cached_embeddings -v`
Expected: FAIL because `hybrid_retrieve_knowledge_chunks` is missing.

- [ ] **Step 3: Extend retrieval implementation**

Add to `retrieval.py`:

```python
import json
import logging
from functools import lru_cache

import numpy as np
from sales_copilot import storage

logger = logging.getLogger(__name__)


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
    except Exception as exc:
        logger.warning("Falling back to keyword retrieval because embedding model failed to load: %s", exc)
        return None


def hybrid_retrieve_knowledge_chunks(db_path, *, source_type: str, query: str, embedder: Embedder | None = None, top_k: int = 3) -> list[dict]:
    rows = storage.list_knowledge_chunks(db_path, source_type=source_type)
    active_embedder = embedder if embedder is not None else load_default_embedder()
    if active_embedder is None:
        return hybrid_retrieve_rows(query, rows, embedder=None, top_k=top_k)

    query_vector = active_embedder.embed_texts([query])[0]
    ranked: list[dict] = []
    keyword_rows = keyword_retrieve(query, rows, top_k=max(top_k, len(rows)))
    keyword_score_map = _normalize_keyword_scores(keyword_rows)

    for row in rows:
        cached = storage.get_knowledge_chunk_embedding(db_path, chunk_id=int(row["id"]), model_name=active_embedder.model_name)
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
        vector_score = cosine_similarity(query_vector, chunk_vector)
        keyword_score = keyword_score_map.get(int(row["id"]), 0.0)
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest D:/minimind/.worktrees/minimind-job-agent/tests/sales_copilot/test_retrieval.py::test_hybrid_retrieve_uses_cached_embeddings -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C D:/minimind/.worktrees/minimind-job-agent add sales_copilot/retrieval.py sales_copilot/storage.py tests/sales_copilot/test_retrieval.py
git -C D:/minimind/.worktrees/minimind-job-agent commit -m "feat: add cache-backed hybrid knowledge retrieval"
```

### Task 4: Integrate hybrid retrieval into the workflow

**Files:**
- Modify: `D:/minimind/.worktrees/minimind-job-agent/sales_copilot/graph.py`
- Test: `D:/minimind/.worktrees/minimind-job-agent/tests/sales_copilot/test_graph.py`

- [ ] **Step 1: Write failing graph integration test**

```python
def test_retrieve_context_node_uses_hybrid_retrieval_metadata(tmp_path, monkeypatch):
    from sales_copilot.graph import retrieve_context_node
    from sales_copilot.storage import init_storage

    db_path = tmp_path / "sales.db"
    init_storage(db_path)

    monkeypatch.setattr(
        "sales_copilot.graph.hybrid_retrieve_knowledge_chunks",
        lambda *args, **kwargs: [
            {
                "id": 1,
                "source_name": "Doc A",
                "chunk_text": "Private deployment",
                "retrieval_mode": "hybrid",
                "vector_score": 0.95,
                "keyword_score": 1.0,
                "hybrid_score": 0.965,
            }
        ],
    )

    result = retrieve_context_node(
        {
            "meeting_summary": {"confirmed_needs": ["private deployment"]},
            "meeting_note_raw": "Need private deployment.",
        },
        database_path=db_path,
    )

    assert result["retrieved_docs"][0]["retrieval_mode"] == "hybrid"
    assert result["workflow_log"][-1] == "retrieve_context"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest D:/minimind/.worktrees/minimind-job-agent/tests/sales_copilot/test_graph.py::test_retrieve_context_node_uses_hybrid_retrieval_metadata -v`
Expected: FAIL because graph still imports old search helpers.

- [ ] **Step 3: Update graph implementation**

In `graph.py`, replace imports:

```python
from sales_copilot.retrieval import hybrid_retrieve_knowledge_chunks
```

Update `retrieve_context_node()` body:

```python
def retrieve_context_node(state: SalesCopilotState, *, llm_client=None, database_path=None) -> dict[str, Any]:
    del llm_client
    query_bits = _normalize_list((state.get("meeting_summary") or {}).get("confirmed_needs"))
    query = " ".join(query_bits).strip() or state.get("meeting_note_raw", "")
    docs: list[dict[str, Any]] = []
    if database_path is not None and query:
        docs.extend(hybrid_retrieve_knowledge_chunks(database_path, source_type="product", query=query, top_k=2))
        docs.extend(hybrid_retrieve_knowledge_chunks(database_path, source_type="playbook", query=query, top_k=2))
    account_id = state.get("account_id")
    if database_path is not None and account_id:
        docs.extend(search_account_history(database_path, account_id)[:2])
    return _step_result(state, "retrieve_context", {"retrieved_docs": docs})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest D:/minimind/.worktrees/minimind-job-agent/tests/sales_copilot/test_graph.py::test_retrieve_context_node_uses_hybrid_retrieval_metadata -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C D:/minimind/.worktrees/minimind-job-agent add sales_copilot/graph.py tests/sales_copilot/test_graph.py
git -C D:/minimind/.worktrees/minimind-job-agent commit -m "feat: integrate hybrid retrieval into workflow"
```

### Task 5: Add embedding rebuild CLI

**Files:**
- Create: `D:/minimind/.worktrees/minimind-job-agent/scripts/rebuild_sales_copilot_embeddings.py`
- Test: `D:/minimind/.worktrees/minimind-job-agent/tests/scripts/test_rebuild_sales_copilot_embeddings.py`

- [ ] **Step 1: Write the failing CLI test**

```python
def test_rebuild_sales_copilot_embeddings_populates_cache(tmp_path):
    from sales_copilot import storage
    from sales_copilot.retrieval import FakeEmbedder
    from scripts.rebuild_sales_copilot_embeddings import rebuild_embeddings

    db_path = tmp_path / "sales.db"
    storage.init_storage(db_path)
    chunk_id = storage.save_knowledge_chunk(
        db_path,
        {
            "source_type": "product",
            "source_name": "Doc A",
            "chunk_text": "Private deployment with audit logging.",
            "tags_json": "[]",
            "retrieval_metadata_json": "{}",
        },
    )

    indexed = rebuild_embeddings(db_path, embedder=FakeEmbedder({"Private deployment with audit logging.": [1.0, 0.0]}))
    row = storage.get_knowledge_chunk_embedding(db_path, chunk_id=chunk_id, model_name="fake-model")

    assert indexed == 1
    assert row is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest D:/minimind/.worktrees/minimind-job-agent/tests/scripts/test_rebuild_sales_copilot_embeddings.py::test_rebuild_sales_copilot_embeddings_populates_cache -v`
Expected: FAIL because script does not exist.

- [ ] **Step 3: Implement the CLI**

Create `scripts/rebuild_sales_copilot_embeddings.py`:

```python
from __future__ import annotations

import argparse
from pathlib import Path

from sales_copilot import storage
from sales_copilot.retrieval import load_default_embedder


def rebuild_embeddings(db_path, *, embedder=None) -> int:
    active_embedder = embedder if embedder is not None else load_default_embedder()
    if active_embedder is None:
        raise RuntimeError("Embedding model is unavailable")

    rows = storage.list_knowledge_chunks(db_path)
    texts = [str(row.get("chunk_text", "")) for row in rows]
    vectors = active_embedder.embed_texts(texts)
    for row, vector in zip(rows, vectors):
        storage.upsert_knowledge_chunk_embedding(
            db_path,
            chunk_id=int(row["id"]),
            model_name=active_embedder.model_name,
            embedding=vector,
        )
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", required=True)
    args = parser.parse_args()
    indexed = rebuild_embeddings(Path(args.db_path))
    print(f"Indexed {indexed} knowledge chunks")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest D:/minimind/.worktrees/minimind-job-agent/tests/scripts/test_rebuild_sales_copilot_embeddings.py::test_rebuild_sales_copilot_embeddings_populates_cache -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C D:/minimind/.worktrees/minimind-job-agent add scripts/rebuild_sales_copilot_embeddings.py tests/scripts/test_rebuild_sales_copilot_embeddings.py
git -C D:/minimind/.worktrees/minimind-job-agent commit -m "feat: add embedding rebuild script"
```

### Task 6: Update docs and run regression verification

**Files:**
- Modify: `D:/minimind/.worktrees/minimind-job-agent/README.md`
- Test: `D:/minimind/.worktrees/minimind-job-agent/tests/sales_copilot/test_retrieval.py`
- Test: `D:/minimind/.worktrees/minimind-job-agent/tests/sales_copilot/test_graph.py`
- Test: `D:/minimind/.worktrees/minimind-job-agent/tests/scripts/test_rebuild_sales_copilot_embeddings.py`

- [ ] **Step 1: Update README usage docs**

Add a short section like:

```md
## Hybrid Retrieval

Sales Copilot now supports hybrid retrieval for product knowledge and sales playbook chunks.

- Vector similarity is provided by `sentence-transformers`
- Keyword retrieval remains as a deterministic fallback
- Cached embeddings are stored in SQLite

Rebuild embeddings:

```bash
python scripts/rebuild_sales_copilot_embeddings.py --db-path data/sales_copilot/sales_copilot.db
```
```

- [ ] **Step 2: Run focused regression tests**

Run: `pytest D:/minimind/.worktrees/minimind-job-agent/tests/sales_copilot/test_retrieval.py D:/minimind/.worktrees/minimind-job-agent/tests/sales_copilot/test_graph.py D:/minimind/.worktrees/minimind-job-agent/tests/scripts/test_rebuild_sales_copilot_embeddings.py -q`
Expected: PASS

- [ ] **Step 3: Run broader sales copilot regression**

Run: `pytest D:/minimind/.worktrees/minimind-job-agent/tests/sales_copilot -q`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git -C D:/minimind/.worktrees/minimind-job-agent add README.md
 git -C D:/minimind/.worktrees/minimind-job-agent commit -m "docs: add hybrid retrieval usage"
```
