import subprocess
import sys
from pathlib import Path

from scripts.job_agent_demo import build_parser, format_job_agent_result, read_text_argument


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


def test_read_text_argument_loads_file_contents_when_path_exists(tmp_path):
    text_file = tmp_path / "resume.txt"
    text_file.write_text("MiniMind resume content", encoding="utf-8")

    loaded = read_text_argument(str(text_file))

    assert loaded == "MiniMind resume content"


def test_build_parser_supports_api_generation_flags():
    parser = build_parser()

    args = parser.parse_args(
        [
            "--company",
            "MiniMind Labs",
            "--role",
            "LLM Application Engineer",
            "--job-posting",
            "job text",
            "--resume-text",
            "resume text",
            "--use-api-generation",
            "--api-base-url",
            "http://127.0.0.1:8998/v1",
            "--api-key",
            "demo-key",
            "--api-model",
            "minimind",
        ]
    )

    assert args.use_api_generation is True
    assert args.api_base_url == "http://127.0.0.1:8998/v1"
    assert args.api_key == "demo-key"
    assert args.api_model == "minimind"


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
