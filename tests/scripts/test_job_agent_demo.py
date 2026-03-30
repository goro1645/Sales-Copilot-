import subprocess
import sys
from pathlib import Path

from scripts.job_agent_demo import format_job_agent_result


def test_format_job_agent_result_surfaces_decision_score_and_application_id():
    summary = format_job_agent_result(
        {
            "match_score": 100,
            "apply_decision": "ready_to_apply",
            "missing_skills": [],
            "rewritten_resume": "Tailored resume text",
            "cover_letter": "Dear MiniMind Labs, ...",
            "application_id": 3,
        }
    )

    assert "Match score: 100" in summary
    assert "Decision: ready_to_apply" in summary
    assert "Application ID: 3" in summary
    assert "Tailored resume text" in summary


def test_job_agent_demo_script_runs_end_to_end(tmp_path):
    project_root = Path(__file__).resolve().parents[2]
    db_path = tmp_path / "applications.db"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/job_agent_demo.py",
            "--company",
            "MiniMind Labs",
            "--role",
            "LLM Application Engineer",
            "--job-posting",
            "Need Python and FastAPI.",
            "--resume-text",
            "Delivered Python and FastAPI based MiniMind applications.",
            "--database-path",
            str(db_path),
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Match score: 100" in result.stdout
    assert "Decision: ready_to_apply" in result.stdout
