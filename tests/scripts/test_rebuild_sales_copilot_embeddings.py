from pathlib import Path

from sales_copilot import storage


def test_rebuild_sales_copilot_embeddings_populates_cache(tmp_path: Path):
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

    indexed = rebuild_embeddings(
        db_path,
        embedder=FakeEmbedder({"Private deployment with audit logging.": [1.0, 0.0]}),
    )
    row = storage.get_knowledge_chunk_embedding(
        db_path,
        chunk_id=chunk_id,
        model_name="fake-model",
    )

    assert indexed == 1
    assert row is not None
