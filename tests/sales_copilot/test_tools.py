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


def test_tokenize_normalizes_text():
    assert tokenize("Private deployment, with SSO!") == ["private", "deployment", "with", "sso"]


def test_ingest_text_file_and_keyword_retrieve(tmp_path: Path):
    db_path = tmp_path / "sales_copilot.db"
    init_storage(db_path)

    chunks = ingest_text_file(
        db_path,
        SAMPLE_PRODUCT_FILE,
        source_type="product",
        source_name="Sample Customer Profile",
    )
    results = keyword_retrieve(db_path, "private deployment sso", source_type="product", limit=3)

    assert chunks
    assert list_knowledge_chunks(db_path)
    assert results[0]["source_name"] == "Sample Customer Profile"
    assert "private deployment" in results[0]["chunk_text"].lower()


def test_seed_knowledge_chunks_and_search_wrappers(tmp_path: Path):
    db_path = tmp_path / "sales_copilot.db"
    init_storage(db_path)

    inserted = seed_knowledge_chunks(db_path)
    product_results = search_product_knowledge(db_path, "private deployment")
    playbook_results = search_sales_playbook(db_path, "discovery questions")

    assert inserted["product"] > 0
    assert inserted["playbook"] > 0
    assert sample_product_chunks()
    assert sample_playbook_chunks()
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

    history = search_account_history(db_path, "Acme Robotics")
    open_tasks = get_open_tasks(db_path, account_name="Acme Robotics")

    assert history["account"]["name"] == "Acme Robotics"
    assert len(history["meetings"]) == 1
    assert len(history["tasks"]) == 1
    assert history["memory"]["recommended_next_step"] == "Book technical demo"
    assert open_tasks[0]["title"] == "Send security checklist"


def test_update_crm_account_writes_log_and_updates_storage(tmp_path: Path):
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

    result = update_crm_account(
        db_path,
        account_id=account_id,
        meeting_id=meeting_id,
        status="paused",
        opportunity_stage="proposal",
        last_contact_at="2026-04-01",
    )

    account = get_account_by_id(db_path, account_id)
    crm_updates = list_crm_updates(db_path)

    assert result["after"]["status"] == "paused"
    assert account["opportunity_stage"] == "proposal"
    assert crm_updates[0]["update_type"] == "account_stage"


def test_merge_and_append_account_memory(tmp_path: Path):
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

    merged = merge_account_memory(
        {
            "confirmed_needs_json": '["private deployment"]',
            "budget_signals_json": '["budget approved"]',
            "timeline_signals_json": '["this quarter"]',
            "decision_makers_json": '["CTO"]',
            "risk_flags_json": '["security_review"]',
            "recommended_next_step": "Book technical demo",
        },
        {
            "confirmed_needs_json": '["private deployment", "on-prem support"]',
            "budget_signals_json": '["procurement ready"]',
            "timeline_signals_json": '["next month"]',
            "decision_makers_json": '["CFO"]',
            "risk_flags_json": '["security_review", "legal_review"]',
            "recommended_next_step": "Send updated proposal",
        },
    )

    append_account_memory(
        db_path,
        account_id=account_id,
        payload={
            "confirmed_needs_json": '["private deployment", "on-prem support"]',
            "budget_signals_json": '["procurement ready"]',
            "timeline_signals_json": '["next month"]',
            "decision_makers_json": '["CFO"]',
            "risk_flags_json": '["security_review", "legal_review"]',
            "recommended_next_step": "Send updated proposal",
        },
    )

    memory = get_account_memory(db_path, account_id)

    assert merged["confirmed_needs_json"] == '["private deployment", "on-prem support"]'
    assert merged["risk_flags_json"] == '["security_review", "legal_review"]'
    assert memory["confirmed_needs_json"] == '["private deployment", "on-prem support"]'
    assert memory["risk_flags_json"] == '["security_review", "legal_review"]'
    assert memory["recommended_next_step"] == "Send updated proposal"
