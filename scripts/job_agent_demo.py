import argparse
import os
import sys
from pathlib import Path

__package__ = "scripts"
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agent.runner import run_job_agent


def read_text_argument(raw_value: str) -> str:
    """Allow the demo to accept either direct text or a path to a text file."""

    candidate = Path(raw_value)
    if candidate.exists() and candidate.is_file():
        return candidate.read_text(encoding="utf-8")
    return raw_value


def format_job_agent_result(result: dict) -> str:
    """Return a screenshot-friendly summary for terminal demos."""

    missing_skills = ", ".join(result.get("missing_skills", [])) or "None"
    return (
        f"Match score: {result['match_score']}\n"
        f"Decision: {result['apply_decision']}\n"
        f"Application ID: {result['application_id']}\n"
        f"Missing skills: {missing_skills}\n\n"
        f"Rewritten resume:\n{result['rewritten_resume']}\n\n"
        f"Cover letter:\n{result['cover_letter']}"
    )


def main():
    parser = argparse.ArgumentParser(description="Run the MiniMind job agent demo")
    parser.add_argument("--company", required=True, help="Company name")
    parser.add_argument("--role", required=True, help="Target role")
    parser.add_argument("--job-posting", required=True, help="Job description text or a file path")
    parser.add_argument("--resume-text", required=True, help="Resume text or a file path")
    parser.add_argument(
        "--database-path",
        default="data/job_agent/applications.db",
        help="SQLite path used to store agent outputs",
    )
    args = parser.parse_args()

    result = run_job_agent(
        company=args.company,
        role=args.role,
        job_posting=read_text_argument(args.job_posting),
        resume_text=read_text_argument(args.resume_text),
        database_path=args.database_path,
    )
    print(format_job_agent_result(result))


if __name__ == "__main__":
    main()
