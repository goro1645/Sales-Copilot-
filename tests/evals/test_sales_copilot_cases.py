import json

import pytest

from evals.sales_copilot.cases import load_golden_cases


def test_load_golden_cases_reads_two_jsonl_records(tmp_path):
    path = tmp_path / "golden_cases.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "case_id": "high_intent_complete",
                        "input_text": "客户想本周确认报价并推进试点。",
                        "expected_parse": {
                            "intent": "high",
                            "confidence": 0.95,
                        },
                        "expected_workflow": {
                            "route": "complete",
                            "required_workflow_fields": [
                                "account_name",
                                "next_step",
                            ],
                        },
                    },
                ),
                json.dumps(
                    {
                        "case_id": "medium_intent_nurture",
                        "input_text": "客户愿意看方案，先发资料。",
                        "expected_parse": {
                            "intent": "medium",
                            "confidence": 0.72,
                        },
                        "expected_workflow": {
                            "route": "nurture",
                            "required_workflow_fields": ["account_name"],
                        },
                    },
                ),
            ]
        ),
        encoding="utf-8",
    )

    cases = load_golden_cases(path)

    assert [case["case_id"] for case in cases] == [
        "high_intent_complete",
        "medium_intent_nurture",
    ]
    assert cases[0]["expected_parse"]["intent"] == "high"
    assert cases[1]["expected_workflow"]["route"] == "nurture"


def test_load_golden_cases_raises_when_required_workflow_fields_missing(tmp_path):
    path = tmp_path / "invalid_golden_cases.jsonl"
    path.write_text(
        json.dumps(
            {
                "case_id": "broken_case",
                "input_text": "客户想先聊聊。",
                "expected_parse": {
                    "intent": "low",
                    "confidence": 0.2,
                },
                "expected_workflow": {
                    "route": "ignore",
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="required_workflow_fields"):
        load_golden_cases(path)
