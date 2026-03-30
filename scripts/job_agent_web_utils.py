from pathlib import Path


def load_sample_documents(data_dir) -> dict:
    """Load the bundled sample JD and resume for the web demo.

    Keeping file IO in a helper makes the Streamlit page easier to read and easier to test.
    """

    data_dir = Path(data_dir)
    return {
        "job_posting": (data_dir / "sample_jd.md").read_text(encoding="utf-8"),
        "resume_text": (data_dir / "sample_resume.md").read_text(encoding="utf-8"),
    }


def build_runner_kwargs(
    *,
    company: str,
    role: str,
    job_posting: str,
    resume_text: str,
    database_path: str,
    use_api_generation: bool,
    api_base_url: str,
    api_key: str,
    api_model: str,
) -> dict:
    """Build one normalized kwargs dict for `run_job_agent`."""

    kwargs = {
        "company": company,
        "role": role,
        "job_posting": job_posting,
        "resume_text": resume_text,
        "database_path": database_path,
        "use_api_generation": use_api_generation,
    }
    if use_api_generation:
        kwargs.update(
            {
                "api_base_url": api_base_url,
                "api_key": api_key,
                "api_model": api_model,
            }
        )
    return kwargs


def build_history_rows(rows: list[dict]) -> list[dict]:
    """Format SQLite rows into a user-facing table shape."""

    return [
        {
            "ID": row["id"],
            "Company": row["company"],
            "Role": row["role"],
            "Score": row["match_score"],
            "Status": row["status"],
            "Resume Version": row["resume_version"],
            "Created At": row["created_at"],
        }
        for row in rows
    ]
