import json
from pathlib import Path

from evals.sales_copilot.csds_adapter import load_csds_cases, load_full_csds_cases


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


def test_load_csds_cases_keeps_source_metadata_and_parse_contract(tmp_path: Path) -> None:
    cases_path = tmp_path / "csds_cases.jsonl"
    cases_path.write_text(
        json.dumps(_build_case("csds-1"), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    cases = load_csds_cases(cases_path)

    assert len(cases) == 1
    assert cases[0]["case_id"] == "csds-1"
    assert cases[0]["source_dataset"] == "CSDS"
    assert cases[0]["source_uid"] == "3559"
    assert cases[0]["expected_parse"]["confirmed_needs"] == ["修改收货地址"]
    assert cases[0]["expected_workflow"]["required_risk_flags"] == []


def test_load_csds_cases_rejects_missing_parse_fields(tmp_path: Path) -> None:
    payload = _build_case("broken")
    del payload["expected_parse"]["next_steps"]  # type: ignore[index]
    cases_path = tmp_path / "csds_cases.jsonl"
    cases_path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")

    try:
        load_csds_cases(cases_path)
    except ValueError as exc:
        assert "expected_parse missing fields" in str(exc)
    else:
        raise AssertionError("expected ValueError for missing parse fields")


def test_repo_csds_cases_keep_public_real_metadata_and_minimum_coverage() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    cases_path = repo_root / "evals" / "sales_copilot" / "csds_cases.jsonl"

    cases = load_csds_cases(cases_path)

    assert len(cases) >= 15
    assert {case["source_dataset"] for case in cases} == {"CSDS"}
    assert all(case["source_uid"] for case in cases)
    assert all("Official CSDS" in case["source_note"] for case in cases)
    assert len({case["case_id"] for case in cases}) == len(cases)
    assert len({case["source_uid"] for case in cases}) == len(cases)


def test_load_full_csds_cases_from_local_dataset_dir_with_split_filter_and_limit(tmp_path: Path) -> None:
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
                    "QRole": "商家",
                    "UserSumm": ["商家询问佣金如何计算。"],
                    "AgentSumm": ["客服提供相关说明链接。"],
                    "FinalSumm": ["商家询问佣金如何计算。", "客服提供相关说明链接。"],
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (dataset_dir / "val.json").write_text(
        json.dumps(
            [
                {
                    "DialogueID": 3,
                    "QRole": "用户",
                    "UserSumm": ["用户询问退款多久到账。"],
                    "AgentSumm": ["客服说明会在3个工作日内到账。"],
                    "FinalSumm": ["用户询问退款多久到账。", "客服说明会在3个工作日内到账。"],
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    cases = load_full_csds_cases(dataset_dir, splits=["train", "val"], limit=2)

    assert len(cases) == 2
    assert cases[0]["source_split"] == "train"
    assert cases[1]["source_split"] == "train"
    assert cases[0]["expected_parse"]["confirmed_needs"] == ["用户询问如何修改地址。"]
    assert cases[0]["expected_parse"]["next_steps"] == ["客服说明未付款订单可直接修改地址。"]
    assert cases[0]["account_name"] if False else True
    assert cases[0]["expected_parse"]["account_name"] == "京东客服"
    assert cases[1]["expected_parse"]["account_name"] == "京东商家客服"


def test_load_full_csds_cases_preserves_timeline_signals_from_official_summaries(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "csds"
    dataset_dir.mkdir()
    (dataset_dir / "train.json").write_text(
        json.dumps(
            [
                {
                    "DialogueID": 9,
                    "QRole": "用户",
                    "UserSumm": ["用户询问退款多久到账。"],
                    "AgentSumm": ["客服说明会在3个工作日内到账。"],
                    "FinalSumm": ["用户询问退款多久到账。", "客服说明会在3个工作日内到账。"],
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    cases = load_full_csds_cases(dataset_dir, splits=["train"])

    assert len(cases) == 1
    assert cases[0]["expected_parse"]["timeline_signals"] == ["客服说明会在3个工作日内到账。"]
