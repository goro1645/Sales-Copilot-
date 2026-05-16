import json
from pathlib import Path
from unittest.mock import patch

from evals.sales_copilot.csds_runner import run_csds_parse_evaluation, run_full_csds_parse_evaluation
from evals.sales_copilot.reporting import write_report_bundle


class ParseOnlyLLM:
    def __init__(self) -> None:
        self.parse_calls = 0

    def complete(self, messages, response_format=None):
        del response_format
        prompt_text = "\n".join(message["content"] for message in messages)
        if "Parse the meeting notes" not in prompt_text:
            raise AssertionError(f"Unexpected prompt: {prompt_text}")
        self.parse_calls += 1
        return json.dumps(
            {
                "account_name": "JD Customer Service",
                "customer_roles": ["user", "agent"],
                "confirmed_needs": ["modify delivery address"],
                "budget_signals": [],
                "timeline_signals": [],
                "next_steps": ["unpaid orders can update the delivery address directly"],
                "competitors": [],
                "risk_flags": [],
            },
            ensure_ascii=False,
        )


def _build_case(case_id: str) -> dict[str, object]:
    return {
        "case_id": case_id,
        "segment": "customer_service_parse_only",
        "source_dataset": "CSDS",
        "source_uid": "3559",
        "source_split": "train",
        "source_note": "Official CSDS FinalSumm adapted into parse-only evaluation input.",
        "customer_profile_text": "Source dataset: CSDS. Account name: JD Customer Service. Conversation roles: user, agent.",
        "meeting_note_text": (
            "Account: JD Customer Service\n"
            "- User asks how to change the address.\n"
            "- Agent explains unpaid orders can update the address directly."
        ),
        "expected_parse": {
            "account_name": "JD Customer Service",
            "customer_roles": ["user", "agent"],
            "confirmed_needs": ["modify delivery address"],
            "budget_signals": [],
            "timeline_signals": [],
            "next_steps": ["unpaid orders can update the delivery address directly"],
            "competitors": [],
        },
        "expected_workflow": {
            "required_risk_flags": [],
        },
    }


def test_run_csds_parse_evaluation_returns_parse_only_bundle(tmp_path: Path) -> None:
    cases_path = tmp_path / "csds_cases.jsonl"
    cases_path.write_text(json.dumps(_build_case("csds-1"), ensure_ascii=False) + "\n", encoding="utf-8")
    llm = ParseOnlyLLM()

    bundle = run_csds_parse_evaluation(
        cases_path=cases_path,
        output_dir=tmp_path / "outputs",
        llm_client=llm,
    )

    assert llm.parse_calls == 1
    assert bundle["report_kind"] == "parse_only"
    assert bundle["dataset_kind"] == "csds"
    assert bundle["summary"]["total_cases"] == 1
    assert "parse" in bundle["summary"]
    assert "workflow" not in bundle["summary"]
    assert bundle["case_results"][0]["parse_metrics"]["json_valid"] is True
    assert bundle["case_results"][0]["parse_result"]["account_name"] == "JD Customer Service"


def test_write_report_bundle_omits_workflow_section_for_parse_only_bundle(tmp_path: Path) -> None:
    cases_path = tmp_path / "csds_cases.jsonl"
    cases_path.write_text(json.dumps(_build_case("csds-1"), ensure_ascii=False) + "\n", encoding="utf-8")

    bundle = run_csds_parse_evaluation(
        cases_path=cases_path,
        output_dir=tmp_path / "outputs",
        llm_client=ParseOnlyLLM(),
    )
    report_dir = Path(write_report_bundle(bundle, tmp_path / "report"))
    report_markdown = (report_dir / "report.md").read_text(encoding="utf-8")

    assert "## Parse Metrics" in report_markdown
    assert "## Workflow Metrics" not in report_markdown


def test_run_full_csds_parse_evaluation_supports_local_dataset_dir_and_limit(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "csds"
    dataset_dir.mkdir()
    (dataset_dir / "train.json").write_text(
        json.dumps(
            [
                {
                    "DialogueID": 1,
                    "QRole": "user",
                    "UserSumm": ["User asks how to change the address."],
                    "AgentSumm": ["Agent says unpaid orders can update the address directly."],
                    "FinalSumm": [
                        "User asks how to change the address.",
                        "Agent says unpaid orders can update the address directly.",
                    ],
                },
                {
                    "DialogueID": 2,
                    "QRole": "user",
                    "UserSumm": ["User asks when the refund will arrive."],
                    "AgentSumm": ["Agent says it will arrive within 3 business days."],
                    "FinalSumm": [
                        "User asks when the refund will arrive.",
                        "Agent says it will arrive within 3 business days.",
                    ],
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    llm = ParseOnlyLLM()
    bundle = run_full_csds_parse_evaluation(
        dataset_dir=dataset_dir,
        output_dir=tmp_path / "outputs",
        llm_client=llm,
        splits=["train"],
        limit=1,
    )

    assert llm.parse_calls == 1
    assert bundle["dataset_kind"] == "full-csds"
    assert bundle["report_kind"] == "parse_only"
    assert bundle["summary"]["total_cases"] == 1
    assert bundle["case_results"][0]["source_split"] == "train"


def test_run_csds_parse_evaluation_reclassifies_when_enabled(tmp_path: Path) -> None:
    cases_path = tmp_path / "csds_cases.jsonl"
    cases_path.write_text(json.dumps(_build_case("csds-1"), ensure_ascii=False) + "\n", encoding="utf-8")
    llm = ParseOnlyLLM()

    with patch(
        "evals.sales_copilot.csds_runner.reclassify_parse_result",
        side_effect=lambda parse_result, llm_client, source_note: {
            **parse_result,
            "timeline_signals": ["after the order is completed"],
        },
    ) as mocked:
        bundle = run_csds_parse_evaluation(
            cases_path=cases_path,
            output_dir=tmp_path / "outputs",
            llm_client=llm,
            use_signal_reclassification=True,
        )

    assert mocked.called
    assert bundle["case_results"][0]["parse_result"]["timeline_signals"] == ["after the order is completed"]


def test_run_csds_parse_evaluation_keeps_parse_result_when_reclassification_fails(tmp_path: Path) -> None:
    cases_path = tmp_path / "csds_cases.jsonl"
    cases_path.write_text(json.dumps(_build_case("csds-1"), ensure_ascii=False) + "\n", encoding="utf-8")
    llm = ParseOnlyLLM()

    with patch(
        "evals.sales_copilot.csds_runner.reclassify_parse_result",
        side_effect=ValueError("signal reclassification failed after retries"),
    ):
        bundle = run_csds_parse_evaluation(
            cases_path=cases_path,
            output_dir=tmp_path / "outputs",
            llm_client=llm,
            use_signal_reclassification=True,
        )

    row = bundle["case_results"][0]
    assert row["parse_result"]["account_name"] == "JD Customer Service"
    assert row["errors"] == []
    assert row["error"] == ""
    assert row["parse_errors"] == []
    assert row["reclassification_errors"] == ["signal reclassification error: signal reclassification failed after retries"]
    assert row["reclassification_error"] == "signal reclassification error: signal reclassification failed after retries"


def test_run_csds_parse_evaluation_candidate_refines_when_enabled(tmp_path: Path) -> None:
    cases_path = tmp_path / "csds_cases.jsonl"
    cases_path.write_text(json.dumps(_build_case("csds-1"), ensure_ascii=False) + "\n", encoding="utf-8")
    llm = ParseOnlyLLM()

    with patch(
        "evals.sales_copilot.csds_runner.refine_parse_result_with_candidates",
        side_effect=lambda parse_result, meeting_note_text, llm_client: {
            **parse_result,
            "timeline_signals": ["after the order is completed"],
        },
    ) as mocked:
        bundle = run_csds_parse_evaluation(
            cases_path=cases_path,
            output_dir=tmp_path / "outputs",
            llm_client=llm,
            use_candidate_generation_refinement=True,
        )

    assert mocked.called
    assert bundle["case_results"][0]["parse_result"]["timeline_signals"] == ["after the order is completed"]
