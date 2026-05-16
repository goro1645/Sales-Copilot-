from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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
