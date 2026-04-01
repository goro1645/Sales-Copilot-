from pathlib import Path

from sales_copilot.storage import (
    get_account_by_id,
    get_account_memory,
    init_storage,
    list_crm_updates,
    list_knowledge_chunks,
    list_tasks,
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


def test_update_crm_account_and_append_account_memory(tmp_path: Path):
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
    upsert_account_memory(
        db_path,
        account_id,
        {
            "confirmed_needs_json": '["private deployment"]',
            "budget_signals_json": "[]",
            "timeline_signals_json": "[]",
            "decision_makers_json": "[]",
            "risk_flags_json": '["security_review"]',
            "recommended_next_step": "Book technical demo",
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
    append_account_memory(
        db_path,
        account_id,
        {
            "confirmed_needs_json": '["private deployment", "on-prem support"]',
            "risk_flags_json": '["security_review", "legal_review"]',
            "recommended_next_step": "Send updated proposal",
        },
    )

    account = get_account_by_id(db_path, account_id)
    crm_updates = list_crm_updates(db_path)
    memory = get_account_memory(db_path, account_id)

    assert update_id == 1
    assert account["opportunity_stage"] == "proposal"
    assert crm_updates[0]["update_type"] == "account_state"
    assert crm_updates[0]["after_json"] == '{"meeting_id": 1, "status": "paused", "opportunity_stage": "proposal", "last_contact_at": "2026-04-01"}'
    assert memory["confirmed_needs_json"] == '["private deployment", "on-prem support"]'
    assert memory["risk_flags_json"] == '["security_review", "legal_review"]'
    assert memory["recommended_next_step"] == "Send updated proposal"


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
