import json

from evals.sales_copilot.signal_reclassifier import (
    apply_signal_fallback,
    annotate_confidence,
    merge_with_confidence,
    extract_signal_candidates,
    project_reclassified_parse_result,
    reclassify_signal_candidates,
)


def test_merge_with_confidence_keeps_budget_addition_even_when_confidence_is_low():
    parse_result = {
        "budget_signals": [],
        "timeline_signals": [],
        "next_steps": [],
    }
    classified = [
        {
            "candidate_id": "sig_001",
            "text": "refund is no longer available for this order",
            "predicted_label": "budget_signals",
            "confidence_score": 0.30,
            "confidence_level": "low",
            "final_labels": ["budget_signals"],
        }
    ]

    merged = merge_with_confidence(parse_result, classified)

    assert merged["budget_signals"] == ["refund is no longer available for this order"]


def test_merge_with_confidence_keeps_action_addition_even_when_confidence_is_low():
    parse_result = {
        "budget_signals": [],
        "timeline_signals": [],
        "next_steps": [],
    }
    classified = [
        {
            "candidate_id": "sig_001",
            "text": "contact support to process the request",
            "predicted_label": "next_steps",
            "confidence_score": 0.35,
            "confidence_level": "low",
            "final_labels": ["next_steps"],
        }
    ]

    merged = merge_with_confidence(parse_result, classified)

    assert merged["next_steps"] == ["contact support to process the request"]


class StubLLMClient:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.calls = []

    def complete(self, messages, response_format=None):
        self.calls.append({"messages": messages, "response_format": response_format})
        return json.dumps(self.response, ensure_ascii=False)

    def complete_with_tool(self, messages, tools, tool_choice):
        self.calls.append({"messages": messages, "tools": tools, "tool_choice": tool_choice})
        return {
            "tool_name": "classify_signal_candidates",
            "arguments": self.response,
        }


class SequencedStubLLMClient:
    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.calls = []

    def complete_with_tool(self, messages, tools, tool_choice):
        self.calls.append({"messages": messages, "tools": tools, "tool_choice": tool_choice})
        if not self.responses:
            raise AssertionError("No more stub responses available")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_extract_signal_candidates_collects_weak_fields_and_objections():
    parse_result = {
        "budget_signals": ["coupon cannot be reused"],
        "timeline_signals": ["after the order is completed"],
        "next_steps": ["leave contact information"],
        "objections": ["the address cannot be edited directly"],
    }

    candidates = extract_signal_candidates(parse_result)

    assert [row["text"] for row in candidates] == [
        "coupon cannot be reused",
        "after the order is completed",
        "leave contact information",
        "the address cannot be edited directly",
    ]


def test_project_reclassified_parse_result_adds_without_clearing_existing_next_steps():
    parse_result = {
        "budget_signals": [],
        "timeline_signals": [],
        "next_steps": ["contact support and leave information"],
    }
    classified = [
        {
            "candidate_id": "sig_001",
            "text": "coupon cannot be reused",
            "predicted_label": "budget_signals",
            "confidence": 0.9,
            "alternative_labels": [],
            "final_labels": ["budget_signals"],
        },
        {
            "candidate_id": "sig_002",
            "text": "after the order is completed",
            "predicted_label": "timeline_signals",
            "confidence": 0.9,
            "alternative_labels": [],
            "final_labels": ["timeline_signals"],
        },
        {
            "candidate_id": "sig_003",
            "text": "leave contact information",
            "predicted_label": "next_steps",
            "confidence": 0.9,
            "alternative_labels": [],
            "final_labels": ["next_steps"],
        },
    ]

    result = project_reclassified_parse_result(parse_result, classified)

    assert result["budget_signals"] == ["coupon cannot be reused"]
    assert result["timeline_signals"] == ["after the order is completed"]
    assert result["next_steps"] == ["contact support and leave information", "leave contact information"]


def test_project_reclassified_parse_result_skips_pure_time_phrase_for_next_steps():
    parse_result = {
        "budget_signals": [],
        "timeline_signals": [],
        "next_steps": ["leave contact information"],
    }
    classified = [
        {
            "candidate_id": "sig_001",
            "text": "after the order is completed",
            "predicted_label": "next_steps",
            "confidence": 1.0,
            "alternative_labels": [],
            "final_labels": ["next_steps", "timeline_signals"],
        }
    ]

    result = project_reclassified_parse_result(parse_result, classified)

    assert result["timeline_signals"] == ["after the order is completed"]
    assert result["next_steps"] == ["leave contact information"]


def test_project_reclassified_parse_result_keeps_action_phrase_in_next_steps():
    parse_result = {
        "budget_signals": [],
        "timeline_signals": [],
        "next_steps": ["leave contact information"],
    }
    classified = [
        {
            "candidate_id": "sig_001",
            "text": "help modify the order after the order is completed",
            "predicted_label": "next_steps",
            "confidence": 1.0,
            "alternative_labels": [],
            "final_labels": ["next_steps", "timeline_signals"],
        }
    ]

    result = project_reclassified_parse_result(parse_result, classified)

    assert result["timeline_signals"] == ["help modify the order after the order is completed"]
    assert result["next_steps"] == [
        "leave contact information",
        "help modify the order after the order is completed",
    ]


def test_reclassify_signal_candidates_uses_llm_response():
    llm_client = StubLLMClient(
        response={
            "classifications": [
                {
                    "candidate_id": "sig_001",
                    "label": "timeline_signals",
                }
            ]
        }
    )
    candidates = [
        {
            "candidate_id": "sig_001",
            "text": "after the order is completed help modify the order",
            "speaker": "agent",
            "evidence": "leave contact information, then help modify the order after the order is completed",
        }
    ]

    rows = reclassify_signal_candidates(
        candidates,
        llm_client=llm_client,
        conversation_context="agent explains that the order can be modified after completion.",
    )

    assert rows[0]["predicted_label"] == "timeline_signals"
    assert rows[0]["text"] == "after the order is completed help modify the order"
    assert llm_client.calls
    assert llm_client.calls[0]["tool_choice"]["function"]["name"] == "classify_signal_candidates"


def test_reclassify_signal_candidates_uses_tool_call_schema():
    llm_client = SequencedStubLLMClient(
        [
            {
                "tool_name": "classify_signal_candidates",
                "arguments": {
                    "classifications": [
                        {"candidate_id": "sig_001", "label": "timeline_signals"},
                    ]
                },
            }
        ]
    )
    candidates = [
        {
            "candidate_id": "sig_001",
            "text": "after the order is completed help modify the order",
            "speaker": "agent",
            "evidence": "leave contact information, then help modify the order after the order is completed",
        }
    ]

    rows = reclassify_signal_candidates(
        candidates,
        llm_client=llm_client,
        conversation_context="agent explains that the order can be modified after completion.",
    )

    assert rows[0]["predicted_label"] == "timeline_signals"
    assert llm_client.calls[0]["tool_choice"]["function"]["name"] == "classify_signal_candidates"
    assert llm_client.calls[0]["tools"][0]["function"]["strict"] is True


def test_reclassify_signal_candidates_retries_after_failed_tool_call():
    llm_client = SequencedStubLLMClient(
        [
            ValueError("missing tool_calls"),
            {
                "tool_name": "classify_signal_candidates",
                "arguments": {
                    "classifications": [
                        {"candidate_id": "sig_001", "label": "next_steps"},
                    ]
                },
            },
        ]
    )
    candidates = [
        {
            "candidate_id": "sig_001",
            "text": "leave contact information",
            "speaker": "agent",
            "evidence": "leave contact information",
        }
    ]

    rows = reclassify_signal_candidates(
        candidates,
        llm_client=llm_client,
        conversation_context="agent asks the user to leave contact information.",
    )

    assert rows[0]["predicted_label"] == "next_steps"
    assert len(llm_client.calls) == 2


def test_apply_signal_fallback_adds_timeline_when_confidence_low():
    classified = [
        {
            "candidate_id": "sig_001",
            "text": "after the order is completed help modify the order",
            "predicted_label": "next_steps",
            "confidence": 0.31,
            "alternative_labels": ["timeline_signals"],
            "notes": "",
        }
    ]

    corrected = apply_signal_fallback(classified)

    assert "timeline_signals" in corrected[0]["final_labels"]


def test_annotate_confidence_marks_pure_time_phrase_as_high():
    classified = [
        {
            "candidate_id": "sig_001",
            "text": "在订单完成后",
            "predicted_label": "timeline_signals",
            "confidence": 1.0,
            "alternative_labels": [],
            "notes": "",
        }
    ]

    annotated = annotate_confidence(classified)

    assert annotated[0]["confidence_level"] == "high"
    assert annotated[0]["confidence_score"] >= 0.75


def test_annotate_confidence_marks_time_and_action_phrase_as_medium():
    classified = [
        {
            "candidate_id": "sig_001",
            "text": "在订单完成后帮助用户完成修改",
            "predicted_label": "next_steps",
            "confidence": 1.0,
            "alternative_labels": [],
            "notes": "",
        }
    ]

    annotated = annotate_confidence(classified)

    assert annotated[0]["confidence_level"] == "medium"
    assert 0.45 <= annotated[0]["confidence_score"] < 0.75


def test_annotate_confidence_marks_vague_phrase_as_low():
    classified = [
        {
            "candidate_id": "sig_001",
            "text": "这个需要核实",
            "predicted_label": "next_steps",
            "confidence": 1.0,
            "alternative_labels": [],
            "notes": "",
        }
    ]

    annotated = annotate_confidence(classified)

    assert annotated[0]["confidence_level"] == "low"
    assert annotated[0]["confidence_score"] < 0.45


def test_merge_with_confidence_removes_pure_time_phrase_from_next_steps_only_for_high_confidence():
    parse_result = {
        "budget_signals": [],
        "timeline_signals": [],
        "next_steps": ["在订单完成后", "联系客服处理"],
    }
    classified = [
        {
            "candidate_id": "sig_001",
            "text": "在订单完成后",
            "predicted_label": "timeline_signals",
            "confidence_score": 0.95,
            "confidence_level": "high",
            "final_labels": ["timeline_signals"],
        },
        {
            "candidate_id": "sig_002",
            "text": "联系客服处理",
            "predicted_label": "next_steps",
            "confidence_score": 0.70,
            "confidence_level": "medium",
            "final_labels": ["next_steps"],
        },
    ]

    merged = merge_with_confidence(parse_result, classified)

    assert merged["timeline_signals"] == ["在订单完成后"]
    assert merged["next_steps"] == ["联系客服处理"]
