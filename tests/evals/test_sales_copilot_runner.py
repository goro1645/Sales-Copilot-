import json
import subprocess
import sys
from pathlib import Path

from evals.sales_copilot.reporting import write_report_bundle
from evals.sales_copilot.runner import run_offline_evaluation
from sales_copilot.storage import list_knowledge_chunks, list_tasks


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


class CountingParseLLM(FakeLLM):
    def __init__(self) -> None:
        self.parse_calls = 0

    def complete(self, messages, response_format=None):
        prompt_text = "\n".join(message["content"] for message in messages)
        if "Parse the meeting notes" in prompt_text:
            self.parse_calls += 1
        return super().complete(messages, response_format=response_format)


class EmptyParseLLM(CountingParseLLM):
    def complete(self, messages, response_format=None):
        prompt_text = "\n".join(message["content"] for message in messages)
        if "Parse the meeting notes" in prompt_text:
            self.parse_calls += 1
            return json.dumps({}, ensure_ascii=False)
        return FakeLLM.complete(self, messages, response_format=response_format)


class ParseCrashLLM(FakeLLM):
    def complete(self, messages, response_format=None):
        prompt_text = "\n".join(message["content"] for message in messages)
        if "Parse the meeting notes" in prompt_text:
            raise RuntimeError("parse crashed")
        return super().complete(messages, response_format=response_format)


class ParseMismatchLLM(FakeLLM):
    def complete(self, messages, response_format=None):
        prompt_text = "\n".join(message["content"] for message in messages)
        if "Parse the meeting notes" in prompt_text:
            return json.dumps(
                {
                    "account_name": "Wrong Account",
                    "customer_roles": [],
                    "confirmed_needs": [],
                    "budget_signals": [],
                    "timeline_signals": [],
                    "next_steps": [],
                    "competitors": [],
                    "risk_flags": [],
                },
                ensure_ascii=False,
            )
        return super().complete(messages, response_format=response_format)


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


def _build_failing_case(case_id: str) -> dict[str, object]:
    case = _build_case(case_id)
    case["segment"] = "medium_intent_nurture"
    case["expected_workflow"] = {
        "lead_score_range": [50, 79],
        "lead_priority": "medium",
        "opportunity_stage": "qualification",
        "expected_route": "standard_follow_up",
        "should_write_crm": False,
        "should_generate_tasks": False,
        "required_task_titles": [],
        "required_risk_flags": [],
    }
    return case


def test_run_offline_evaluation_returns_case_results_and_summary(tmp_path: Path):
    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(json.dumps(_build_case("case-1"), ensure_ascii=False) + "\n", encoding="utf-8")

    bundle = run_offline_evaluation(
        cases_path=cases_path,
        output_dir=tmp_path / "outputs",
        llm_client=FakeLLM(),
    )

    assert bundle["summary"]["total_cases"] == 1
    assert "parse" in bundle["summary"]
    assert "workflow" in bundle["summary"]
    assert "parse_summary" not in bundle["summary"]
    assert "workflow_summary" not in bundle["summary"]
    assert len(bundle["case_results"]) == 1
    assert bundle["case_results"][0]["case_id"] == "case-1"
    assert bundle["case_results"][0]["parse_metrics"]["json_valid"] is True
    assert bundle["case_results"][0]["workflow_metrics"]["workflow_success"] is True
    assert bundle["case_results"][0]["workflow_result"]["crm_update_ids"]
    assert list_knowledge_chunks(bundle["case_results"][0]["database_path"])


def test_run_offline_evaluation_supports_mcp_mode(tmp_path: Path):
    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(json.dumps(_build_case("case-mcp"), ensure_ascii=False) + "\n", encoding="utf-8")

    bundle = run_offline_evaluation(
        cases_path=cases_path,
        output_dir=tmp_path / "outputs",
        llm_client=FakeLLM(),
        execution_mode="mcp",
    )

    case_result = bundle["case_results"][0]
    tasks = list_tasks(case_result["database_path"])
    assert bundle["summary"]["workflow"]["workflow_success_rate"] == 1.0
    assert case_result["workflow_metrics"]["workflow_success"] is True
    assert case_result["workflow_result"]["crm_update_ids"] == []
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Send proposal"


def test_run_offline_evaluation_reuses_single_parse_result_for_workflow(tmp_path: Path):
    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(json.dumps(_build_case("case-1"), ensure_ascii=False) + "\n", encoding="utf-8")
    llm = CountingParseLLM()

    bundle = run_offline_evaluation(
        cases_path=cases_path,
        output_dir=tmp_path / "outputs",
        llm_client=llm,
    )

    assert llm.parse_calls == 1
    assert bundle["case_results"][0]["parse_result"]["account_name"] == "Acme Robotics"
    assert bundle["case_results"][0]["workflow_result"]["dashboard_output"]["account_name"] == "Acme Robotics"


def test_run_offline_evaluation_does_not_reparse_when_first_parse_is_empty_dict(tmp_path: Path):
    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(json.dumps(_build_case("case-empty-parse"), ensure_ascii=False) + "\n", encoding="utf-8")
    llm = EmptyParseLLM()

    bundle = run_offline_evaluation(
        cases_path=cases_path,
        output_dir=tmp_path / "outputs",
        llm_client=llm,
    )

    assert llm.parse_calls == 1
    assert bundle["case_results"][0]["parse_result"] == {}


def test_run_offline_evaluation_keeps_failing_case_in_summary_and_report(tmp_path: Path):
    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(
        "\n".join(
            [
                json.dumps(_build_case("case-pass"), ensure_ascii=False),
                json.dumps(_build_failing_case("case-fail"), ensure_ascii=False),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    bundle = run_offline_evaluation(
        cases_path=cases_path,
        output_dir=tmp_path / "outputs",
        llm_client=FakeLLM(),
    )
    report_dir = Path(write_report_bundle(bundle, tmp_path / "report"))
    report_markdown = (report_dir / "report.md").read_text(encoding="utf-8")

    assert bundle["summary"]["total_cases"] == 2
    assert len(bundle["case_results"]) == 2
    assert any(row["case_id"] == "case-fail" for row in bundle["case_results"])
    assert any(row["workflow_metrics"]["workflow_success"] is True for row in bundle["case_results"])
    assert "Top Failing Cases" in report_markdown
    assert "case-fail" in report_markdown
    assert "priority mismatch" in report_markdown.lower()
    assert "stage mismatch" in report_markdown.lower()
    assert "crm writeback mismatch" in report_markdown.lower()
    assert "task generation mismatch" in report_markdown.lower()


def test_run_offline_evaluation_keeps_exception_case_in_results_and_report(tmp_path: Path):
    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(json.dumps(_build_case("case-error"), ensure_ascii=False) + "\n", encoding="utf-8")

    bundle = run_offline_evaluation(
        cases_path=cases_path,
        output_dir=tmp_path / "outputs",
        llm_client=ParseCrashLLM(),
    )
    report_dir = Path(write_report_bundle(bundle, tmp_path / "report"))
    report_markdown = (report_dir / "report.md").read_text(encoding="utf-8")

    assert bundle["summary"]["total_cases"] == 1
    assert len(bundle["case_results"]) == 1
    assert bundle["case_results"][0]["case_id"] == "case-error"
    assert bundle["case_results"][0]["error"]
    assert bundle["case_results"][0]["workflow_metrics"]["workflow_success"] is False
    assert bundle["summary"]["workflow"]["workflow_success_rate"] == 0.0
    assert "case-error" in report_markdown
    assert "case execution error" in report_markdown.lower()


def test_write_report_bundle_marks_parse_metric_failures_even_when_json_is_valid(tmp_path: Path):
    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(json.dumps(_build_case("case-parse-miss"), ensure_ascii=False) + "\n", encoding="utf-8")

    bundle = run_offline_evaluation(
        cases_path=cases_path,
        output_dir=tmp_path / "outputs",
        llm_client=ParseMismatchLLM(),
    )
    report_dir = Path(write_report_bundle(bundle, tmp_path / "report"))
    report_markdown = (report_dir / "report.md").read_text(encoding="utf-8")

    assert bundle["case_results"][0]["parse_metrics"]["json_valid"] is True
    assert bundle["case_results"][0]["parse_metrics"]["field_exact_match"]["account_name"] is False
    assert "Top Failing Cases" in report_markdown
    assert "- None" not in report_markdown
    assert "case-parse-miss" in report_markdown
    assert "account name mismatch" in report_markdown.lower()


def test_write_report_bundle_does_not_flag_missing_tasks_when_not_applicable(tmp_path: Path):
    bundle = {
        "summary": {
            "total_cases": 1,
            "parse": {
                "json_valid_rate": 1.0,
                "list_field_precision": 1.0,
                "list_field_recall": 1.0,
                "list_field_f1": 1.0,
                "average_list_field_f1": 1.0,
                "risk_flag_recall": 0.0,
                "field_exact_match_rate": {"account_name": 1.0},
            },
            "workflow": {
                "workflow_success_rate": 1.0,
                "route_accuracy": 1.0,
                "priority_accuracy": 1.0,
                "stage_accuracy": 1.0,
                "score_range_accuracy": 1.0,
                "crm_writeback_accuracy": 1.0,
                "task_generation_hit_rate": 1.0,
                "required_task_hit_rate": 0.0,
            },
        },
        "case_results": [
            {
                "case_id": "case-no-task",
                "segment": "low_intent_or_noise",
                "parse_metrics": {
                    "json_valid": True,
                    "field_exact_match": {"account_name": True},
                    "list_field_precision": {},
                    "list_field_recall": {},
                    "list_field_f1": {},
                    "list_field_applicable": {},
                    "risk_flag_recall": 0.0,
                    "risk_flag_applicable": False,
                },
                "workflow_metrics": {
                    "workflow_success": True,
                    "route_correct": True,
                    "priority_correct": True,
                    "stage_correct": True,
                    "score_in_range": True,
                    "crm_writeback_correct": True,
                    "task_generation_correct": True,
                    "required_task_hit_rate": 0.0,
                    "required_task_applicable": False,
                },
            }
        ],
    }

    report_dir = Path(write_report_bundle(bundle, tmp_path / "report"))
    report_markdown = (report_dir / "report.md").read_text(encoding="utf-8")

    assert "case-no-task" not in report_markdown
    assert "required tasks missing" not in report_markdown.lower()
    assert "- None" in report_markdown


def test_write_report_bundle_writes_json_md_and_jsonl(tmp_path: Path):
    bundle = {
        "summary": {
            "total_cases": 1,
            "parse": {
                "json_valid_rate": 1.0,
                "list_field_precision": 1.0,
                "list_field_recall": 1.0,
                "list_field_f1": 1.0,
                "average_list_field_f1": 1.0,
            },
            "workflow": {"workflow_success_rate": 1.0, "route_accuracy": 1.0},
        },
        "case_results": [
            {
                "case_id": "case-1",
                "segment": "high_intent_complete",
                "database_path": str(tmp_path / "case-1.db"),
                "parse_metrics": {"json_valid": True, "field_exact_match": {"account_name": True}},
                "workflow_metrics": {"workflow_success": True, "route_correct": True},
                "parse_result": {"account_name": "Acme Robotics"},
                "workflow_result": {"lead_score": 88},
            }
        ],
    }

    report_dir = Path(write_report_bundle(bundle, tmp_path / "report"))

    report_json = report_dir / "report.json"
    report_md = report_dir / "report.md"
    case_results_jsonl = report_dir / "case_results.jsonl"

    assert report_dir.parent == tmp_path / "report"
    assert report_dir.name.isdigit()
    assert report_json.exists()
    assert report_md.exists()
    assert case_results_jsonl.exists()
    assert '"total_cases": 1' in report_json.read_text(encoding="utf-8")
    report_markdown = report_md.read_text(encoding="utf-8")
    assert "# Sales Copilot Offline Eval Report" in report_markdown
    assert "dataset size" in report_markdown.lower()
    assert "segment distribution" in report_markdown.lower()
    assert "list_field_precision" in report_markdown
    assert "list_field_recall" in report_markdown
    assert "list_field_f1" in report_markdown
    assert "average_list_field_f1" in report_markdown
    assert "route_accuracy" in report_markdown
    assert '"case_id": "case-1"' in case_results_jsonl.read_text(encoding="utf-8")


def test_run_sales_copilot_eval_cli_help_works_from_repo_root():
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "run_sales_copilot_eval.py"
    completed = subprocess.run(
        [sys.executable, str(script_path), "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "Run Sales Copilot offline evaluation." in completed.stdout
    assert "--cases" in completed.stdout
    assert "--execution-mode" in completed.stdout
    assert "--mode" in completed.stdout
