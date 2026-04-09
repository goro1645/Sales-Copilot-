from pathlib import Path

from sales_copilot import storage


def test_upsert_and_get_knowledge_chunk_embedding(tmp_path: Path):
    db_path = tmp_path / "sales.db"
    storage.init_storage(db_path)
    chunk_id = storage.save_knowledge_chunk(
        db_path,
        {
            "source_type": "product",
            "source_name": "Demo Product",
            "chunk_text": "Private deployment and audit logging.",
            "tags_json": '["deployment"]',
            "retrieval_metadata_json": "{}",
        },
    )

    storage.upsert_knowledge_chunk_embedding(
        db_path,
        chunk_id=chunk_id,
        model_name="fake-model",
        embedding=[0.1, 0.2, 0.3],
    )

    row = storage.get_knowledge_chunk_embedding(
        db_path,
        chunk_id=chunk_id,
        model_name="fake-model",
    )

    assert row is not None
    assert row["chunk_id"] == chunk_id
    assert row["model_name"] == "fake-model"
    assert row["embedding"] == [0.1, 0.2, 0.3]


def test_hybrid_retrieve_prefers_vector_signal_when_available():
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


def test_hybrid_retrieve_uses_cached_embeddings(tmp_path: Path):
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
    storage.upsert_knowledge_chunk_embedding(
        db_path,
        chunk_id=chunk_id,
        model_name="fake-model",
        embedding=[1.0, 0.0],
    )

    embedder = FakeEmbedder({"private deployment": [1.0, 0.0]})
    results = hybrid_retrieve_knowledge_chunks(
        db_path,
        source_type="product",
        query="private deployment",
        embedder=embedder,
        top_k=1,
    )

    assert results[0]["id"] == chunk_id
    assert results[0]["retrieval_mode"] == "hybrid"


def test_hybrid_rerank_reorders_top_k_candidates():
    from sales_copilot.retrieval import FakeEmbedder, hybrid_rerank_retrieve_rows
    from sales_copilot.reranker import FakeReranker

    rows = [
        {"id": 1, "chunk_text": "Private deployment with audit logging.", "source_name": "Doc A", "tags_json": "[]"},
        {"id": 2, "chunk_text": "Private deployment architecture and CRM integration.", "source_name": "Doc B", "tags_json": "[]"},
    ]
    embedder = FakeEmbedder(
        {
            "private deployment and crm integration": [1.0, 0.0],
            "Private deployment with audit logging.": [1.0, 0.0],
            "Private deployment architecture and CRM integration.": [0.9, 0.0],
        }
    )
    reranker = FakeReranker(
        {
            ("private deployment and crm integration", "Private deployment with audit logging."): 0.1,
            ("private deployment and crm integration", "Private deployment architecture and CRM integration."): 0.95,
        }
    )

    results = hybrid_rerank_retrieve_rows(
        "private deployment and crm integration",
        rows,
        embedder=embedder,
        reranker=reranker,
        top_k=2,
    )

    assert results[0]["source_name"] == "Doc B"
    assert results[0]["retrieval_mode"] == "hybrid_rerank"
    assert results[0]["rerank_score"] > results[1]["rerank_score"]
