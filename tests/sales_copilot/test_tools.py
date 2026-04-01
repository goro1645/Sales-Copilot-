from pathlib import Path
import json

import pytest

from sales_copilot.storage import (
    get_account_by_id,
    get_account_memory,
    init_storage,
    list_crm_updates,
    list_knowledge_chunks,
    list_tasks,
    list_meeting_records,
    save_account,
    save_meeting_record,
    save_task_record,
    upsert_account_memory,
)
from sales_copilot.tools import (
    append_account_memory,
    get_open_tasks,
    ingest_text_file,
    keyword_retrieve,
    merge_account_memory,
    sample_playbook_chunks,
    sample_product_chunks,
    search_account_history,
    search_product_knowledge,
    search_sales_playbook,
    seed_knowledge_chunks,
    tokenize,
    update_crm_account,
)


DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "sales_copilot"
SAMPLE_PRODUCT_FILE = DATA_DIR / "sample_customer_profile.md"
SAMPLE_MEETING_FILE = DATA_DIR / "sample_meeting_note.md"


def test_ingest_text_file_reads_file_metadata_without_db():
    payload = ingest_text_file(SAMPLE_MEETING_FILE)

    assert payload["filename"] == "sample_meeting_note.md"
    assert payload["source_path"] == str(SAMPLE_MEETING_FILE)
    assert "private deployment" in payload["text"].lower()
    assert "blocks" not in payload


def test_tokenize_normalizes_text():
    assert tokenize("Private deployment, with SSO!") == ["private", "deployment", "with", "sso"]


def test_keyword_retrieve_ranks_rows_lexically():
    rows = [
        {
            "id": 1,
            "source_name": "Playbook",
            "chunk_text": "Ask about discovery questions and timeline",
            "tags": ["discovery", "timeline"],
        },
        {
            "id": 2,
            "source_name": "Product Brief",
            "chunk_text": "Private deployment and SSO are supported",
            "tags": ["deployment", "sso"],
        },
    ]

    ranked = keyword_retrieve("private deployment sso", rows, top_k=1)

    assert ranked[0]["id"] == 2
    assert ranked[0]["score"] > 0
    assert keyword_retrieve("missing term", rows, top_k=3) == []


def test_seed_helpers_and_search_wrappers(tmp_path: Path):
    db_path = tmp_path / "sales_copilot.db"
    init_storage(db_path)

    seed_knowledge_chunks(db_path, sample_product_chunks() + sample_playbook_chunks())

    product_results = search_product_knowledge(db_path, "private deployment")
    playbook_results = search_sales_playbook(db_path, "discovery questions")
    stored_chunks = list_knowledge_chunks(db_path)

    assert len(stored_chunks) == len(sample_product_chunks()) + len(sample_playbook_chunks())
    assert product_results
    assert playbook_results


def test_search_product_knowledge_returns_seeded_product_section(tmp_path: Path):
    db_path = tmp_path / "sales_copilot.db"
    init_storage(db_path)
    seed_knowledge_chunks(db_path, sample_product_chunks())

    rows = search_product_knowledge(db_path, "private deployment and sso", top_k=1)

    assert rows[0]["source_type"] == "product"
    assert rows[0]["source_name"] == "Sales Copilot Product Brief"
    assert json.loads(rows[0]["retrieval_metadata_json"])["section"] == "deployment"


def test_search_sales_playbook_returns_seeded_playbook_section(tmp_path: Path):
    db_path = tmp_path / "sales_copilot.db"
    init_storage(db_path)
    seed_knowledge_chunks(db_path, sample_playbook_chunks())

    rows = search_sales_playbook(db_path, "security review checklist and technical demo", top_k=1)

    assert rows[0]["source_type"] == "playbook"
    assert rows[0]["source_name"] == "Enterprise Sales Playbook"
    assert json.loads(rows[0]["retrieval_metadata_json"])["section"] == "objections"


def test_search_account_history_and_open_tasks(tmp_path: Path):
    db_path = tmp_path / "sales_copilot.db"
    account_id = save_account(
        db_path,
        {
            "name": "Acme Robotics",
            "industry": "Manufacturing",
            "size_segment": "Mid-Market",
            "status": "active",
            "opportunity_stage": "discovery",
        },
    )
    meeting_id = save_meeting_record(
        db_path,
        {
            "account_id": account_id,
            "meeting_title": "Discovery Call",
            "meeting_note_raw": "CTO asked for private deployment and SSO.",
            "meeting_summary_json": '{"confirmed_needs": ["private deployment"], "risk_flags": ["security_review"]}',
            "lead_score": 90,
            "priority": "high",
        },
    )
    save_task_record(
        db_path,
        {
            "account_id": account_id,
            "meeting_id": meeting_id,
            "title": "Send security checklist",
            "description": "Share deployment and SSO details",
            "priority": "high",
            "due_at": "2026-04-03",
            "status": "open",
        },
    )
    upsert_account_memory(
        db_path,
        account_id,
        {
            "confirmed_needs_json": '["private deployment"]',
            "budget_signals_json": '["budget approved"]',
            "timeline_signals_json": '["this quarter"]',
            "decision_makers_json": '["CTO"]',
            "risk_flags_json": '["security_review"]',
            "recommended_next_step": "Book technical demo",
        },
    )

    history = search_account_history(db_path, account_id)
    open_tasks = get_open_tasks(db_path, account_id)

    assert len(history) == 1
    assert history[0]["meeting_title"] == "Discovery Call"
    assert open_tasks[0]["title"] == "Send security checklist"


def test_get_open_tasks_keeps_same_title_for_different_meetings(tmp_path: Path):
    db_path = tmp_path / "sales_copilot.db"
    account_id = save_account(
        db_path,
        {
            "name": "Acme Robotics",
            "industry": "Manufacturing",
            "size_segment": "Mid-Market",
            "status": "active",
            "opportunity_stage": "discovery",
        },
    )
    first_meeting_id = save_meeting_record(
        db_path,
        {
            "account_id": account_id,
            "meeting_title": "Discovery Call",
            "meeting_note_raw": "CTO asked for private deployment and SSO.",
            "meeting_summary_json": '{"confirmed_needs": ["private deployment"]}',
            "lead_score": 90,
            "priority": "high",
        },
    )
    second_meeting_id = save_meeting_record(
        db_path,
        {
            "account_id": account_id,
            "meeting_title": "Procurement Review",
            "meeting_note_raw": "CFO asked about pricing and timing.",
            "meeting_summary_json": '{"confirmed_needs": ["pricing"]}',
            "lead_score": 82,
            "priority": "high",
        },
    )
    save_task_record(
        db_path,
        {
            "account_id": account_id,
            "meeting_id": first_meeting_id,
            "title": "Send proposal",
            "description": "Send first proposal",
            "priority": "high",
            "due_at": "2026-04-03",
            "status": "open",
        },
    )
    save_task_record(
        db_path,
        {
            "account_id": account_id,
            "meeting_id": second_meeting_id,
            "title": "Send proposal",
            "description": "Send updated proposal",
            "priority": "high",
            "due_at": "2026-04-03",
            "status": "open",
        },
    )

    open_tasks = get_open_tasks(db_path, account_id)

    assert len(open_tasks) == 2
    assert {task["meeting_id"] for task in open_tasks} == {first_meeting_id, second_meeting_id}


def test_get_open_tasks_returns_empty_list_for_missing_account(tmp_path: Path):
    db_path = tmp_path / "sales_copilot.db"
    init_storage(db_path)

    assert get_open_tasks(db_path, 999) == []


def test_seed_knowledge_chunks_dedupes_rows_in_same_batch(tmp_path: Path):
    db_path = tmp_path / "sales_copilot.db"
    init_storage(db_path)
    rows = sample_product_chunks()[:1]

    seed_knowledge_chunks(db_path, rows + rows)

    stored_chunks = list_knowledge_chunks(db_path)
    assert len(stored_chunks) == 1


def test_update_crm_account_keeps_account_unchanged_on_invalid_meeting(tmp_path: Path):
    db_path = tmp_path / "sales_copilot.db"
    account_id = save_account(
        db_path,
        {
            "name": "Northwind Traders",
            "industry": "Retail",
            "size_segment": "Enterprise",
            "status": "active",
            "opportunity_stage": "discovery",
        },
    )

    try:
        update_crm_account(
            db_path,
            account_id,
            {
                "meeting_id": 999,
                "status": "paused",
                "opportunity_stage": "proposal",
                "last_contact_at": "2026-04-01",
            },
        )
        raised = False
    except Exception:
        raised = True

    account = get_account_by_id(db_path, account_id)
    assert raised
    assert account["status"] == "active"
    assert account["opportunity_stage"] == "discovery"


def test_update_crm_account_keeps_account_unchanged_on_cross_account_meeting(tmp_path: Path):
    db_path = tmp_path / "sales_copilot.db"
    account_one_id = save_account(
        db_path,
        {
            "name": "Northwind Traders",
            "industry": "Retail",
            "size_segment": "Enterprise",
            "status": "active",
            "opportunity_stage": "discovery",
        },
    )
    account_two_id = save_account(
        db_path,
        {
            "name": "Acme Robotics",
            "industry": "Manufacturing",
            "size_segment": "Mid-Market",
            "status": "active",
            "opportunity_stage": "qualification",
        },
    )
    meeting_id = save_meeting_record(
        db_path,
        {
            "account_id": account_two_id,
            "meeting_title": "Discovery Call",
            "meeting_note_raw": "Discussed deployment.",
            "meeting_summary_json": '{"confirmed_needs": ["private deployment"]}',
            "lead_score": 88,
            "priority": "high",
        },
    )

    with pytest.raises(Exception):
        update_crm_account(
            db_path,
            account_one_id,
            {
                "meeting_id": meeting_id,
                "status": "paused",
                "opportunity_stage": "proposal",
                "last_contact_at": "2026-04-01",
            },
        )

    account = get_account_by_id(db_path, account_one_id)
    assert account["status"] == "active"
    assert account["opportunity_stage"] == "discovery"


def test_update_crm_account_saves_normalized_after_payload(tmp_path: Path):
    db_path = tmp_path / "sales_copilot.db"
    account_id = save_account(
        db_path,
        {
            "name": "Northwind Traders",
            "industry": "Retail",
            "size_segment": "Enterprise",
            "status": "active",
            "opportunity_stage": "discovery",
        },
    )
    meeting_id = save_meeting_record(
        db_path,
        {
            "account_id": account_id,
            "meeting_title": "Proposal Review",
            "meeting_note_raw": "Discussed pricing and timing.",
            "meeting_summary_json": '{"confirmed_needs": ["pricing"]}',
            "lead_score": 75,
            "priority": "medium",
        },
    )

    update_id = update_crm_account(
        db_path,
        account_id,
        {
            "meeting_id": meeting_id,
            "status": "paused",
            "opportunity_stage": "proposal",
            "last_contact_at": "2026-04-01",
        },
    )

    account = get_account_by_id(db_path, account_id)
    crm_updates = list_crm_updates(db_path)

    assert update_id == 1
    assert account["opportunity_stage"] == "proposal"
    assert crm_updates[0]["update_type"] == "account_state"
    assert crm_updates[0]["after_json"] == '{"meeting_id": 1, "status": "paused", "opportunity_stage": "proposal", "last_contact_at": "2026-04-01"}'


def test_merge_account_memory_dedupes_confirmed_needs_and_risk_flags():
    merged = merge_account_memory(
        {
            "confirmed_needs_json": '["private deployment"]',
            "risk_flags_json": '["security_review"]',
            "recommended_next_step": "Book technical demo",
        },
        {
            "confirmed_needs_json": '["private deployment", "on-prem support"]',
            "risk_flags_json": '["security_review", "legal_review"]',
            "recommended_next_step": "Send updated proposal",
        },
    )

    assert merged["confirmed_needs_json"] == '["private deployment", "on-prem support"]'
    assert merged["risk_flags_json"] == '["security_review", "legal_review"]'
    assert merged["recommended_next_step"] == "Send updated proposal"
