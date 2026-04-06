import json
from pathlib import Path

from evals.sales_copilot.csds_adapter import load_csds_cases


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
