from pathlib import Path

from agent.graph import build_job_agent_graph
from agent.storage import save_application_record


def run_job_agent(
    *,
    company: str,
    role: str,
    job_posting: str,
    resume_text: str,
    database_path,
    required_skills: list[str] | None = None,
    preferred_skills: list[str] | None = None,
) -> dict:
    """Run the current graph once and persist the final decision.

    This wrapper gives the demo and later UI a single entrypoint. Keeping orchestration here
    avoids spreading graph invocation and SQLite code across multiple scripts.
    """

    graph = build_job_agent_graph()
    result = graph.invoke(
        {
            "company": company,
            "role": role,
            "job_posting": job_posting,
            "resume_text": resume_text,
            "required_skills": required_skills or [],
            "preferred_skills": preferred_skills or [],
        }
    )

    resume_version = "resume_auto_v1"
    if result.get("apply_decision") == "reject":
        resume_version = "resume_original"

    application_id = save_application_record(
        db_path=Path(database_path),
        record={
            "company": company,
            "role": role,
            "match_score": result["match_score"],
            "status": result["apply_decision"],
            "resume_version": resume_version,
            "cover_letter": result.get("cover_letter", ""),
        },
    )
    result["application_id"] = application_id
    return result
