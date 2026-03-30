from agent.runner import run_job_agent
from agent.storage import init_storage, list_application_records, save_application_record


def test_save_application_record_persists_rows_in_sqlite(tmp_path):
    db_path = tmp_path / "applications.db"
    init_storage(db_path)

    record_id = save_application_record(
        db_path=db_path,
        record={
            "company": "MiniMind Labs",
            "role": "LLM Application Engineer",
            "match_score": 88,
            "status": "ready_to_apply",
            "resume_version": "resume_v2",
            "cover_letter": "Hello from MiniMind",
        },
    )

    rows = list_application_records(db_path)

    assert record_id == 1
    assert len(rows) == 1
    assert rows[0]["company"] == "MiniMind Labs"
    assert rows[0]["role"] == "LLM Application Engineer"


def test_run_job_agent_persists_final_result_and_returns_application_id(tmp_path):
    db_path = tmp_path / "applications.db"

    result = run_job_agent(
        company="MiniMind Labs",
        role="LLM Application Engineer",
        job_posting="Need Python and FastAPI.",
        resume_text="Delivered Python and FastAPI based MiniMind applications.",
        database_path=db_path,
        required_skills=["python", "fastapi"],
        preferred_skills=["streamlit"],
    )

    rows = list_application_records(db_path)

    assert result["apply_decision"] == "ready_to_apply"
    assert result["application_id"] == 1
    assert len(rows) == 1
    assert rows[0]["status"] == "ready_to_apply"
