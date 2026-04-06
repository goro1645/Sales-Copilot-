import json
import subprocess
from pathlib import Path

from evals.sales_copilot.reporting import write_report_bundle
from evals.sales_copilot.runner import run_offline_evaluation
from sales_copilot.storage import list_knowledge_chunks


class FakeLLM:
    def complete(self, messages, response_format=None):
        del response_format
        prompt_text = "\n".join(message["content"] for message in messages)
        if "Parse the meeting notes" in prompt_text:
            return json.dumps(
                {
                    "account_name": "Acme Robotics",
                    "customer_roles": ["CTO"],
                    "confirmed_needs": ["private deployment"],
                    "budget_signals": ["budget approved"],
                    "timeline_signals": ["this quarter"],
                    "next_steps": ["Send proposal"],
                    "competitors": [],
                    "risk_flags": [],
                },
                ensure_ascii=False,
            )
        if "Evaluate the lead" in prompt_text:
            return json.dumps(
                {
                    "lead_score": 88,
                    "lead_priority": "high",
                    "opportunity_stage": "proposal",
                    "risk_flags": [],
                },
                ensure_ascii=False,
            )
        if "follow-up plan" in prompt_text.lower():
            return json.dumps(
                {
                    "summary": "Send proposal",
                    "tasks": [
                        {
                            "title": "Send proposal",
                            "description": "Send tailored proposal",
                            "priority": "high",
                            "due_at": "2026-04-10",
                        }
                    ],
                },
                ensure_ascii=False,
            )
        raise AssertionError(f"Unexpected prompt: {prompt_text}")


def _build_case(case_id: str) -> dict[str, object]:
    return {
        "case_id": case_id,
        "segment": "high_intent_complete",
        "customer_profile_text": "Acme Robotics is evaluating a private deployment option.",
        "meeting_note_text": "The CTO confirmed budget approval and wants a proposal this quarter.",
        "expected_parse": {
            "account_name": "Acme Robotics",
            "customer_roles": ["CTO"],
            "confirmed_needs": ["private deployment"],
            "budget_signals": ["budget approved"],
            "timeline_signals": ["this quarter"],
            "next_steps": ["Send proposal"],
            "competitors": [],
        },
        "expected_workflow": {
            "lead_score_range": [80, 100],
            "lead_priority": "high",
            "opportunity_stage": "proposal",
            "expected_route": "high_priority_follow_up",
            "should_write_crm": True,
            "should_generate_tasks": True,
            "required_task_titles": ["Send proposal"],
            "required_risk_flags": [],
        },
    }


def test_run_offline_evaluation_returns_case_results_and_summary(tmp_path: Path):
    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(json.dumps(_build_case("case-1"), ensure_ascii=False) + "\n", encoding="utf-8")

    bundle = run_offline_evaluation(
        cases_path=cases_path,
        output_dir=tmp_path / "outputs",
        llm_client=FakeLLM(),
    )

    assert bundle["summary"]["total_cases"] == 1
    assert "parse_summary" in bundle["summary"]
    assert "workflow_summary" in bundle["summary"]
    assert len(bundle["case_results"]) == 1
    assert bundle["case_results"][0]["case_id"] == "case-1"
    assert bundle["case_results"][0]["parse_metrics"]["json_valid"] is True
    assert bundle["case_results"][0]["workflow_metrics"]["workflow_success"] is True
    assert bundle["case_results"][0]["workflow_result"]["crm_update_ids"]
    assert list_knowledge_chunks(bundle["case_results"][0]["database_path"])


def test_write_report_bundle_writes_json_md_and_jsonl(tmp_path: Path):
    bundle = {
        "summary": {
            "total_cases": 1,
            "parse_summary": {"json_valid_rate": 1.0},
            "workflow_summary": {"workflow_success_rate": 1.0},
        },
        "case_results": [
            {
                "case_id": "case-1",
                "segment": "high_intent_complete",
                "database_path": str(tmp_path / "case-1.db"),
                "parse_metrics": {"json_valid": True},
                "workflow_metrics": {"workflow_success": True},
                "parse_result": {"account_name": "Acme Robotics"},
                "workflow_result": {"lead_score": 88},
            }
        ],
    }

    paths = write_report_bundle(bundle, tmp_path / "report")

    report_json = Path(paths["report_json"])
    report_md = Path(paths["report_md"])
    case_results_jsonl = Path(paths["case_results_jsonl"])

    assert report_json.exists()
    assert report_md.exists()
    assert case_results_jsonl.exists()
    assert '"total_cases": 1' in report_json.read_text(encoding="utf-8")
    assert "# Sales Copilot Offline Eval Report" in report_md.read_text(encoding="utf-8")
    assert '"case_id": "case-1"' in case_results_jsonl.read_text(encoding="utf-8")


def test_run_sales_copilot_eval_cli_help_works_from_repo_root():
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "run_sales_copilot_eval.py"
    completed = subprocess.run(
        ["D:\\anaconda\\envs\\minimind_job_agent\\python.exe", str(script_path), "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "Run Sales Copilot offline evaluation." in completed.stdout
