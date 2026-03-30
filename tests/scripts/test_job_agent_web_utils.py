from scripts.job_agent_web_utils import (
    build_history_rows,
    build_runner_kwargs,
    load_sample_documents,
)


def test_load_sample_documents_reads_both_sample_files(tmp_path):
    data_dir = tmp_path / "job_agent"
    data_dir.mkdir(parents=True)
    (data_dir / "sample_jd.md").write_text("JD content", encoding="utf-8")
    (data_dir / "sample_resume.md").write_text("Resume content", encoding="utf-8")

    docs = load_sample_documents(data_dir)

    assert docs["job_posting"] == "JD content"
    assert docs["resume_text"] == "Resume content"


def test_build_runner_kwargs_adds_api_settings_only_when_enabled():
    kwargs = build_runner_kwargs(
        company="MiniMind Labs",
        role="LLM Application Engineer",
        job_posting="Need Python and FastAPI.",
        resume_text="Built MiniMind apps.",
        database_path="data/job_agent/applications.db",
        use_api_generation=True,
        api_base_url="http://127.0.0.1:8998/v1",
        api_key="demo-key",
        api_model="minimind",
    )

    assert kwargs["company"] == "MiniMind Labs"
    assert kwargs["use_api_generation"] is True
    assert kwargs["api_base_url"] == "http://127.0.0.1:8998/v1"
    assert kwargs["api_key"] == "demo-key"
    assert kwargs["api_model"] == "minimind"


def test_build_history_rows_formats_saved_records_for_table_display():
    rows = build_history_rows(
        [
            {
                "id": 3,
                "company": "MiniMind Labs",
                "role": "LLM Application Engineer",
                "match_score": 100,
                "status": "ready_to_apply",
                "resume_version": "resume_auto_v1",
                "created_at": "2026-03-30 21:00:00",
            }
        ]
    )

    assert rows == [
        {
            "ID": 3,
            "Company": "MiniMind Labs",
            "Role": "LLM Application Engineer",
            "Score": 100,
            "Status": "ready_to_apply",
            "Resume Version": "resume_auto_v1",
            "Created At": "2026-03-30 21:00:00",
        }
    ]
