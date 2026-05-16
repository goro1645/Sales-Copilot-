# Sales Copilot Hybrid Retrieval Design

## Goal

Upgrade Sales Copilot from keyword-only retrieval to hybrid retrieval, where vector similarity is the primary ranking signal and existing keyword retrieval remains as a deterministic fallback and blending signal. The design should preserve the current demo and evaluation flows while making the project's RAG story more defensible.

## Scope

This iteration only upgrades retrieval for product knowledge and sales playbook chunks already stored in SQLite. Account history retrieval remains unchanged. We do not introduce an external vector database in this phase.

## Current State

- `sales_copilot/tools.py` uses `keyword_retrieve()` for product and playbook search.
- `sales_copilot/graph.py` calls `search_product_knowledge()` and `search_sales_playbook()` inside `retrieve_context_node()`.
- Knowledge chunks already live in SQLite via `knowledge_chunks`.

## Proposed Architecture

### 1. Retrieval module
Create `sales_copilot/retrieval.py` to isolate embedding-based retrieval logic.

Responsibilities:
- load an embedding model through a small provider interface
- generate embeddings for query text and knowledge chunks
- cache embeddings in SQLite
- compute vector similarity scores
- combine vector similarity with keyword scores into a final hybrid ranking
- expose retrieval metadata for workflow logs and UI

### 2. Embedding cache in SQLite
Extend storage with a new table for cached knowledge chunk embeddings.

Table:
- `knowledge_chunk_embeddings`
  - `chunk_id`
  - `model_name`
  - `embedding_json`
  - `updated_at`
  - unique key on `(chunk_id, model_name)`

This keeps the implementation local and reproducible without introducing Chroma or FAISS yet.

### 3. Hybrid ranking
For each candidate knowledge chunk:
- compute keyword score using existing token overlap logic
- compute vector similarity using cosine similarity
- normalize both signals
- produce `hybrid_score`

Ranking behavior:
- prefer vector similarity when available
- keep keyword overlap as a secondary signal
- if embedding generation fails or model is unavailable, fall back to keyword-only retrieval

Returned retrieval docs should include:
- `retrieval_mode` (`hybrid`, `vector_only`, or `keyword_only`)
- `vector_score`
- `keyword_score`
- `hybrid_score`
- `matched_terms`

### 4. Workflow integration
Update `retrieve_context_node()` in `sales_copilot/graph.py` so that:
- product knowledge and sales playbook retrieval go through the new hybrid retrieval layer
- account history retrieval continues to use the existing path
- the combined `retrieved_docs` payload keeps enough metadata for debugging and display

### 5. Indexing script
Create `scripts/rebuild_sales_copilot_embeddings.py`.

Responsibilities:
- read all product and playbook chunks from SQLite
- generate embeddings for missing or stale rows
- store embeddings in `knowledge_chunk_embeddings`
- print summary counts for indexed chunks

## Embedding Provider Strategy

Use a provider interface so tests do not depend on a real downloaded model.

Two provider modes:
- production provider backed by `sentence-transformers`
- fake embedder used by tests, returning deterministic vectors

This keeps runtime behavior realistic while making automated tests stable and fast.

## Error Handling

- If the embedding model cannot load, retrieval logs the reason and falls back to keyword-only mode.
- If a specific chunk has no cached embedding, it can still participate through keyword scoring.
- If the query embedding fails, the whole retrieval call falls back to keyword-only mode.
- Retrieval code must never block the rest of the workflow from continuing.

## Testing Strategy

### Unit tests
- vector similarity ranking with fake embedder
- hybrid blending order
- keyword fallback when embedder is unavailable
- embedding cache read/write behavior

### Integration tests
- `retrieve_context_node()` returns hybrid retrieval metadata
- workflow still succeeds when vector retrieval is unavailable
- indexing script populates cache for product and playbook chunks

## Non-Goals

- no external vector database
- no retrieval evaluation benchmark in this iteration
- no change to account history retrieval logic
- no multi-model embedding configuration UI

## Expected Outcome

After this change, Sales Copilot will support hybrid retrieval over local knowledge chunks, making the project closer to a defensible vector-backed RAG design while preserving the reliability of the current keyword-based flow.
