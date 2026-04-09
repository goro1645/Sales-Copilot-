from __future__ import annotations

import json
from datetime import datetime as real_datetime
from pathlib import Path

import pytest

from evals.sales_copilot.retrieval_runner import load_retrieval_cases, run_retrieval_benchmark
from sales_copilot.retrieval import FakeEmbedder
from sales_copilot.reranker import FakeReranker
from sales_copilot.tools import sample_product_chunks, seed_knowledge_chunks
from scripts.run_sales_copilot_retrieval_eval import main as run_retrieval_eval_main, write_retrieval_report


def test_load_retrieval_cases_reads_repository_dataset_and_preserves_order():
    path = Path(__file__).resolve().parents[2] / "evals" / "sales_copilot" / "retrieval_cases.jsonl"

    cases = load_retrieval_cases(path)

    assert len(cases) == 12
    assert [case["case_id"] for case in cases] == [
        "product_account_memory",
        "product_private_deployment",
        "product_crm_sync",
        "product_workflow_deterministic",
        "product_security_controls",
        "product_shared_deployment",
        "playbook_discovery_questions",
        "playbook_security_review",
        "playbook_next_step_proposal",
        "playbook_task_discipline",
        "playbook_customer_memory",
        "playbook_follow_up_owner",
    ]
    assert [case["source_type"] for case in cases[:6]] == ["product"] * 6
    assert [case["source_type"] for case in cases[6:]] == ["playbook"] * 6
    assert cases[0]["expected_chunk_ids"] == [1]
    assert cases[1]["expected_chunk_ids"] == [2]
    assert cases[2]["expected_chunk_ids"] == [3]
    assert cases[3]["expected_chunk_ids"] == [1]
    assert cases[4]["expected_chunk_ids"] == [2]
    assert cases[5]["expected_chunk_ids"] == [2]
    assert cases[6]["expected_chunk_ids"] == [4]
    assert cases[-1]["expected_chunk_ids"] == [6]


def test_load_retrieval_cases_rejects_invalid_source_type(tmp_path: Path):
    path = tmp_path / "bad_source_type.jsonl"
    path.write_text(
        json.dumps(
            {
                "case_id": "bad-source",
                "query": "private deployment",
                "source_type": "crm",
                "expected_chunk_ids": [2],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="source_type"):
        load_retrieval_cases(path)


def test_load_retrieval_cases_rejects_non_positive_chunk_ids(tmp_path: Path):
    path = tmp_path / "bad_chunk_ids.jsonl"
    path.write_text(
        json.dumps(
            {
                "case_id": "bad-chunks",
                "query": "security review",
                "source_type": "playbook",
                "expected_chunk_ids": [0, 4],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="expected_chunk_ids"):
        load_retrieval_cases(path)


def test_load_retrieval_cases_rejects_duplicate_case_ids(tmp_path: Path):
    path = tmp_path / "duplicate_case_ids.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "case_id": "dup-case",
                        "query": "private deployment",
                        "source_type": "product",
                        "expected_chunk_ids": [2],
                    }
                ),
                json.dumps(
                    {
                        "case_id": "dup-case",
                        "query": "security review",
                        "source_type": "playbook",
                        "expected_chunk_ids": [5],
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unique"):
        load_retrieval_cases(path)


def test_run_retrieval_benchmark_defaults_to_production_hybrid_path(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "sales.db"
    seed_knowledge_chunks(db_path, sample_product_chunks())
    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(
        '{"case_id":"product_memory","query":"account memory and tracked follow-up actions","source_type":"product","expected_chunk_ids":[1]}\n',
        encoding="utf-8",
    )

    marker = object()
    captured: dict[str, object] = {}

    def fake_hybrid_retrieve_knowledge_chunks(
        db_path,
        *,
        source_type: str,
        query: str,
        top_k: int = 5,
        embedder=marker,
    ):
        captured["db_path"] = Path(db_path)
        captured["source_type"] = source_type
        captured["query"] = query
        captured["embedder"] = embedder
        return [{"id": 2}, {"id": 1}]

    monkeypatch.setattr("evals.sales_copilot.retrieval_runner.hybrid_retrieve_knowledge_chunks", fake_hybrid_retrieve_knowledge_chunks)

    results = run_retrieval_benchmark(cases_path=cases_path, db_path=db_path)

    assert captured["db_path"] == db_path
    assert captured["source_type"] == "product"
    assert captured["query"] == "account memory and tracked follow-up actions"
    assert captured["embedder"] is marker
    assert results["case_results"][0]["modes"]["keyword_only"]["ranked_chunk_ids"][0] == 1
    assert results["case_results"][0]["modes"]["hybrid"]["ranked_chunk_ids"] == [2, 1]


def test_run_retrieval_benchmark_accepts_injected_embedder_and_changes_hybrid_ranking(tmp_path: Path):
    db_path = tmp_path / "sales.db"
    seed_knowledge_chunks(db_path, sample_product_chunks())
    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(
        '{"case_id":"product_memory","query":"account memory and tracked follow-up actions","source_type":"product","expected_chunk_ids":[1]}\n',
        encoding="utf-8",
    )

    embedder = FakeEmbedder(
        {
            "account memory and tracked follow-up actions": [1.0, 0.0],
            "Sales Copilot helps account teams capture meeting notes, keep account memory fresh, and turn follow-up actions into tracked work.\n\nThe workflow is deterministic and storage-backed, so the same inputs always produce the same outputs.": [
                0.0,
                1.0,
            ],
            "Deployment options include private deployment for security-sensitive teams, plus standard shared deployment for lighter use cases.\n\nSecurity teams often ask about SSO, audit logging, and how customer data is isolated.": [
                1.0,
                0.0,
            ],
            "CRM sync writes account stage changes, meeting summaries, and next-step notes back through the storage layer.\n\nThis keeps the sales record consistent without needing model calls.": [
                0.0,
                1.0,
            ],
        }
    )

    results = run_retrieval_benchmark(
        cases_path=cases_path,
        db_path=db_path,
        embedder=embedder,
    )

    assert "keyword_only" in results["summary"]
    assert "hybrid" in results["summary"]
    assert results["case_results"][0]["modes"]["keyword_only"]["ranked_chunk_ids"][0] == 1
    assert results["case_results"][0]["modes"]["hybrid"]["ranked_chunk_ids"][0] == 2
    assert results["case_results"][0]["modes"]["hybrid"]["ranked_chunk_ids"] != results["case_results"][0]["modes"]["keyword_only"]["ranked_chunk_ids"]


def test_run_retrieval_benchmark_reports_hybrid_rerank_mode(tmp_path: Path):
    db_path = tmp_path / "sales.db"
    seed_knowledge_chunks(db_path, sample_product_chunks())
    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(
        '{"case_id":"product_deployment","query":"private deployment and crm integration","source_type":"product","expected_chunk_ids":[2]}\n',
        encoding="utf-8",
    )

    embedder = FakeEmbedder(
        {
            "private deployment and crm integration": [1.0, 0.0],
            "Sales Copilot helps account teams capture meeting notes, keep account memory fresh, and turn follow-up actions into tracked work.\n\nThe workflow is deterministic and storage-backed, so the same inputs always produce the same outputs.": [1.0, 0.0],
            "Deployment options include private deployment for security-sensitive teams, plus standard shared deployment for lighter use cases.\n\nSecurity teams often ask about SSO, audit logging, and how customer data is isolated.": [0.95, 0.0],
            "CRM sync writes account stage changes, meeting summaries, and next-step notes back through the storage layer.\n\nThis keeps the sales record consistent without needing model calls.": [0.90, 0.0],
        }
    )
    reranker = FakeReranker(
        {
            (
                "private deployment and crm integration",
                "Sales Copilot helps account teams capture meeting notes, keep account memory fresh, and turn follow-up actions into tracked work.\n\nThe workflow is deterministic and storage-backed, so the same inputs always produce the same outputs.",
            ): 0.05,
            (
                "private deployment and crm integration",
                "Deployment options include private deployment for security-sensitive teams, plus standard shared deployment for lighter use cases.\n\nSecurity teams often ask about SSO, audit logging, and how customer data is isolated.",
            ): 0.95,
            (
                "private deployment and crm integration",
                "CRM sync writes account stage changes, meeting summaries, and next-step notes back through the storage layer.\n\nThis keeps the sales record consistent without needing model calls.",
            ): 0.80,
        }
    )

    results = run_retrieval_benchmark(
        cases_path=cases_path,
        db_path=db_path,
        embedder=embedder,
        reranker=reranker,
    )

    assert "hybrid_rerank" in results["summary"]
    assert results["case_results"][0]["modes"]["hybrid_rerank"]["ranked_chunk_ids"][0] == 2


def test_write_retrieval_report_creates_report_files(tmp_path: Path):
    output_dir = tmp_path / "outputs"
    payload = {
        "summary": {"keyword_only": {"num_cases": 1}, "hybrid": {"num_cases": 1}},
        "case_results": [{"case_id": "case-1"}],
    }

    paths = write_retrieval_report(output_dir=output_dir, payload=payload)

    assert paths["report_json"].exists()
    assert paths["report_md"].exists()
    assert paths["case_results_jsonl"].exists()
    assert paths["report_json"].parent == output_dir
    assert paths["report_md"].parent == output_dir
    assert paths["case_results_jsonl"].parent == output_dir


def test_run_retrieval_eval_cli_writes_timestamped_report_dir(monkeypatch, tmp_path: Path):
    output_dir = tmp_path / "eval-output"
    cases_path = tmp_path / "cases.jsonl"
    db_path = tmp_path / "sales.db"
    cases_path.write_text(
        "\n".join(
            [
                '{"case_id":"case-1","query":"demo","source_type":"product","expected_chunk_ids":[1]}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    payload = {
        "summary": {"keyword_only": {"num_cases": 1}, "hybrid": {"num_cases": 1}},
        "case_results": [{"case_id": "case-1"}],
    }

    called = {}

    def fake_run_retrieval_benchmark(*, cases_path, db_path):
        called["cases_path"] = Path(cases_path)
        called["db_path"] = Path(db_path)
        return payload

    class FakeDatetime:
        @classmethod
        def now(cls):
            return real_datetime(2026, 4, 9, 12, 34, 56)

    monkeypatch.setattr("scripts.run_sales_copilot_retrieval_eval.run_retrieval_benchmark", fake_run_retrieval_benchmark)
    monkeypatch.setattr("scripts.run_sales_copilot_retrieval_eval.dt.datetime", FakeDatetime)
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_sales_copilot_retrieval_eval.py",
            "--cases",
            str(cases_path),
            "--db-path",
            str(db_path),
            "--output-dir",
            str(output_dir),
        ],
    )

    exit_code = run_retrieval_eval_main()

    assert exit_code == 0
    assert called["cases_path"] == cases_path
    assert called["db_path"] == db_path
    report_dir = output_dir / "20260409123456"
    assert (report_dir / "report.json").exists()
    assert (report_dir / "report.md").exists()
    assert (report_dir / "case_results.jsonl").exists()
