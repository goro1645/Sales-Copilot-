import json
from pathlib import Path

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
                "account_name": "京东客服",
                "customer_roles": ["用户", "客服"],
                "confirmed_needs": ["修改收货地址"],
                "budget_signals": [],
                "timeline_signals": [],
                "next_steps": ["未付款订单可直接修改地址"],
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
        "customer_profile_text": "来源数据集：CSDS。账户名称：京东客服。会话角色：用户、客服。",
        "meeting_note_text": "账户：京东客服\n- 用户询问地址写错怎么处理。\n- 客服回答未付款订单可直接修改地址。",
        "expected_parse": {
            "account_name": "京东客服",
            "customer_roles": ["用户", "客服"],
            "confirmed_needs": ["修改收货地址"],
            "budget_signals": [],
            "timeline_signals": [],
            "next_steps": ["未付款订单可直接修改地址"],
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
    assert bundle["case_results"][0]["parse_result"]["account_name"] == "京东客服"


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
                    "QRole": "用户",
                    "UserSumm": ["用户询问如何修改地址。"],
                    "AgentSumm": ["客服说明未付款订单可直接修改地址。"],
                    "FinalSumm": ["用户询问如何修改地址。", "客服说明未付款订单可直接修改地址。"],
                },
                {
                    "DialogueID": 2,
                    "QRole": "用户",
                    "UserSumm": ["用户询问退款多久到账。"],
                    "AgentSumm": ["客服说明会在3个工作日内到账。"],
                    "FinalSumm": ["用户询问退款多久到账。", "客服说明会在3个工作日内到账。"],
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
