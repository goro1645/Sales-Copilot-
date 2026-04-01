import sqlite3
from pathlib import Path

import pytest

from sales_copilot.storage import (
    get_account_by_id,
    get_account_memory,
    init_storage,
    list_accounts,
    list_crm_updates,
    list_knowledge_chunks,
    list_meeting_records,
    list_tasks,
    save_account,
    save_crm_update,
    save_knowledge_chunk,
    save_meeting_record,
    save_task_record,
    update_account_stage_and_status,
    upsert_account_memory,
)


def test_storage_creates_tables_and_persists_accounts(tmp_path: Path):
    db_path = tmp_path / "sales_copilot.db"

    init_storage(db_path)
    save_account(
        db_path,
        {
            "name": "Acme Robotics",
            "industry": "Manufacturing",
            "size_segment": "Mid-Market",
            "status": "active",
            "opportunity_stage": "discovery",
        },
    )

    rows = list_accounts(db_path)

    assert len(rows) == 1
    assert rows[0]["name"] == "Acme Robotics"
    assert rows[0]["opportunity_stage"] == "discovery"


def test_storage_can_read_and_update_accounts(tmp_path: Path):
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

    before = get_account_by_id(db_path, account_id)
    update_account_stage_and_status(
        db_path,
        account_id=account_id,
        status="paused",
        opportunity_stage="proposal",
        last_contact_at="2026-04-01",
    )
    after = get_account_by_id(db_path, account_id)

    assert before["status"] == "active"
    assert after["status"] == "paused"
    assert after["opportunity_stage"] == "proposal"
    assert after["last_contact_at"] == "2026-04-01"


def test_storage_returns_none_for_missing_account(tmp_path: Path):
    db_path = tmp_path / "sales_copilot.db"
    init_storage(db_path)

    assert get_account_by_id(db_path, 999) is None


def test_storage_rejects_updates_for_missing_account(tmp_path: Path):
    db_path = tmp_path / "sales_copilot.db"
    init_storage(db_path)

    with pytest.raises(ValueError):
        update_account_stage_and_status(
            db_path,
            account_id=999,
            status="paused",
            opportunity_stage="proposal",
            last_contact_at="2026-04-01",
        )


def test_storage_supports_meetings_tasks_memory_and_crm_updates(tmp_path: Path):
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
            "meeting_note_raw": "CTO asked for deployment options.",
            "meeting_summary_json": '{"confirmed_needs": ["private deployment"]}',
            "lead_score": 88,
            "priority": "high",
        },
    )
    save_task_record(
        db_path,
        {
            "account_id": account_id,
            "meeting_id": meeting_id,
            "title": "Send proposal",
            "description": "Send tailored proposal before Friday",
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
    save_crm_update(
        db_path,
        {
            "account_id": account_id,
            "meeting_id": meeting_id,
            "update_type": "account_stage",
            "before_json": '{"opportunity_stage": "discovery"}',
            "after_json": '{"opportunity_stage": "proposal"}',
        },
    )

    meeting_rows = list_meeting_records(db_path)
    task_rows = list_tasks(db_path)
    memory_row = get_account_memory(db_path, account_id)
    crm_rows = list_crm_updates(db_path)

    assert meeting_rows[0]["priority"] == "high"
    assert task_rows[0]["status"] == "open"
    assert memory_row["recommended_next_step"] == "Book technical demo"
    assert crm_rows[0]["update_type"] == "account_stage"


def test_storage_rejects_invalid_foreign_keys(tmp_path: Path):
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
            "meeting_note_raw": "CTO asked for deployment options.",
            "meeting_summary_json": '{"confirmed_needs": ["private deployment"]}',
            "lead_score": 88,
            "priority": "high",
        },
    )

    with pytest.raises(sqlite3.IntegrityError):
        save_meeting_record(
            db_path,
            {
                "account_id": 999,
                "meeting_title": "Invalid Call",
                "meeting_note_raw": "Bad account id.",
                "meeting_summary_json": "{}",
                "lead_score": 10,
                "priority": "low",
            },
        )

    with pytest.raises(sqlite3.IntegrityError):
        save_task_record(
            db_path,
            {
                "account_id": 999,
                "meeting_id": meeting_id,
                "title": "Broken task account",
                "description": "Invalid account reference",
                "priority": "low",
                "due_at": "2026-04-03",
                "status": "open",
            },
        )

    with pytest.raises(sqlite3.IntegrityError):
        save_task_record(
            db_path,
            {
                "account_id": account_id,
                "meeting_id": 999,
                "title": "Broken task",
                "description": "Invalid meeting reference",
                "priority": "low",
                "due_at": "2026-04-03",
                "status": "open",
            },
        )

    with pytest.raises(sqlite3.IntegrityError):
        upsert_account_memory(
            db_path,
            999,
            {
                "confirmed_needs_json": "[]",
                "budget_signals_json": "[]",
                "timeline_signals_json": "[]",
                "decision_makers_json": "[]",
                "risk_flags_json": "[]",
                "recommended_next_step": "None",
            },
        )

    with pytest.raises(sqlite3.IntegrityError):
        save_crm_update(
            db_path,
            {
                "account_id": account_id,
                "meeting_id": 999,
                "update_type": "account_stage",
                "before_json": "{}",
                "after_json": "{}",
            },
        )

    assert meeting_id == 1


def test_storage_rejects_task_cross_account_mismatch(tmp_path: Path):
    db_path = tmp_path / "sales_copilot.db"
    account_one_id = save_account(
        db_path,
        {
            "name": "Acme Robotics",
            "industry": "Manufacturing",
            "size_segment": "Mid-Market",
            "status": "active",
            "opportunity_stage": "discovery",
        },
    )
    account_two_id = save_account(
        db_path,
        {
            "name": "Northwind Traders",
            "industry": "Retail",
            "size_segment": "Enterprise",
            "status": "active",
            "opportunity_stage": "proposal",
        },
    )
    meeting_id = save_meeting_record(
        db_path,
        {
            "account_id": account_two_id,
            "meeting_title": "Proposal Review",
            "meeting_note_raw": "Discussed pricing.",
            "meeting_summary_json": '{"confirmed_needs": ["pricing"]}',
            "lead_score": 75,
            "priority": "medium",
        },
    )

    with pytest.raises(sqlite3.IntegrityError):
        save_task_record(
            db_path,
            {
                "account_id": account_one_id,
                "meeting_id": meeting_id,
                "title": "Cross-account task",
                "description": "Should not attach to another account's meeting",
                "priority": "low",
                "due_at": "2026-04-03",
                "status": "open",
            },
        )


def test_storage_rejects_crm_update_cross_account_mismatch(tmp_path: Path):
    db_path = tmp_path / "sales_copilot.db"
    account_one_id = save_account(
        db_path,
        {
            "name": "Acme Robotics",
            "industry": "Manufacturing",
            "size_segment": "Mid-Market",
            "status": "active",
            "opportunity_stage": "discovery",
        },
    )
    account_two_id = save_account(
        db_path,
        {
            "name": "Northwind Traders",
            "industry": "Retail",
            "size_segment": "Enterprise",
            "status": "active",
            "opportunity_stage": "proposal",
        },
    )
    meeting_id = save_meeting_record(
        db_path,
        {
            "account_id": account_two_id,
            "meeting_title": "Proposal Review",
            "meeting_note_raw": "Discussed pricing.",
            "meeting_summary_json": '{"confirmed_needs": ["pricing"]}',
            "lead_score": 75,
            "priority": "medium",
        },
    )

    with pytest.raises(sqlite3.IntegrityError):
        save_crm_update(
            db_path,
            {
                "account_id": account_one_id,
                "meeting_id": meeting_id,
                "update_type": "account_stage",
                "before_json": '{"opportunity_stage": "discovery"}',
                "after_json": '{"opportunity_stage": "proposal"}',
            },
        )


def test_storage_overwrites_account_memory_on_second_upsert(tmp_path: Path):
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
    upsert_account_memory(
        db_path,
        account_id,
        {
            "confirmed_needs_json": '["on-prem support"]',
            "budget_signals_json": '["budget approved", "procurement ready"]',
            "timeline_signals_json": '["next month"]',
            "decision_makers_json": '["CFO"]',
            "risk_flags_json": '["legal_review"]',
            "recommended_next_step": "Send updated proposal",
        },
    )

    memory_row = get_account_memory(db_path, account_id)

    assert memory_row["confirmed_needs_json"] == '["on-prem support"]'
    assert memory_row["decision_makers_json"] == '["CFO"]'
    assert memory_row["recommended_next_step"] == "Send updated proposal"


def test_storage_persists_knowledge_chunks_with_source_filter(tmp_path: Path):
    db_path = tmp_path / "sales_copilot.db"
    save_knowledge_chunk(
        db_path,
        {
            "source_type": "product",
            "source_name": "Deployment Guide",
            "chunk_text": "Supports private deployment.",
            "tags_json": '["deployment"]',
            "retrieval_metadata_json": '{"rank": 1}',
        },
    )
    save_knowledge_chunk(
        db_path,
        {
            "source_type": "playbook",
            "source_name": "Discovery Playbook",
            "chunk_text": "Ask about technical requirements.",
            "tags_json": '["discovery"]',
            "retrieval_metadata_json": '{"rank": 2}',
        },
    )

    all_chunks = list_knowledge_chunks(db_path)
    product_chunks = list_knowledge_chunks(db_path, source_type="product")

    assert len(all_chunks) == 2
    assert len(product_chunks) == 1
    assert product_chunks[0]["source_name"] == "Deployment Guide"
