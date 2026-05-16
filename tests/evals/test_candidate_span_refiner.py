from __future__ import annotations

from evals.sales_copilot.candidate_span_refiner import (
    generate_signal_candidates,
    refine_parse_result_with_candidates,
    score_candidate,
)


class StubLLMClient:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.calls = []

    def complete_with_tool(self, messages, tools, tool_choice):
        self.calls.append({"messages": messages, "tools": tools, "tool_choice": tool_choice})
        return {
            "tool_name": "propose_signal_candidates",
            "arguments": self.response,
        }


def test_generate_signal_candidates_uses_tool_call_schema():
    llm = StubLLMClient(
        {
            "candidates": [
                {
                    "candidate_id": "cand_001",
                    "text": "在订单完成后",
                    "coarse_label": "timeline_signals",
                }
            ]
        }
    )

    candidates = generate_signal_candidates(
        meeting_note_text="用户可以留下信息，在订单完成后帮助用户完成修改。",
        parse_result={"next_steps": ["用户可以留下信息，在订单完成后帮助用户完成修改"]},
        llm_client=llm,
    )

    assert candidates[0]["text"] == "在订单完成后"
    assert llm.calls[0]["tool_choice"]["function"]["name"] == "propose_signal_candidates"
    assert llm.calls[0]["tools"][0]["function"]["strict"] is True


def test_generate_signal_candidates_discards_non_source_spans():
    llm = StubLLMClient(
        {
            "candidates": [
                {
                    "candidate_id": "cand_001",
                    "text": "在订单完成后",
                    "coarse_label": "timeline_signals",
                },
                {
                    "candidate_id": "cand_002",
                    "text": "虚构片段",
                    "coarse_label": "timeline_signals",
                },
            ]
        }
    )

    candidates = generate_signal_candidates(
        meeting_note_text="用户可以留下信息，在订单完成后帮助用户完成修改。",
        parse_result={},
        llm_client=llm,
    )

    assert [row["text"] for row in candidates] == ["在订单完成后"]


def test_score_candidate_prefers_short_pure_timeline_span():
    short_score = score_candidate(
        {
            "candidate_id": "cand_001",
            "text": "在订单完成后",
            "coarse_label": "timeline_signals",
        }
    )
    long_score = score_candidate(
        {
            "candidate_id": "cand_002",
            "text": "用户可以留下信息，在订单完成后帮助用户完成修改",
            "coarse_label": "timeline_signals",
        }
    )

    assert short_score > long_score


def test_refine_parse_result_with_candidates_only_updates_budget_and_timeline():
    llm = StubLLMClient(
        {
            "candidates": [
                {
                    "candidate_id": "cand_001",
                    "text": "在订单完成后",
                    "coarse_label": "timeline_signals",
                },
                {
                    "candidate_id": "cand_002",
                    "text": "不能再使用优惠券",
                    "coarse_label": "budget_signals",
                },
                {
                    "candidate_id": "cand_003",
                    "text": "帮助用户完成修改",
                    "coarse_label": "next_steps",
                },
            ]
        }
    )
    parse_result = {
        "budget_signals": [],
        "timeline_signals": [],
        "next_steps": ["用户可以留下信息，在订单完成后帮助用户完成修改"],
    }

    refined = refine_parse_result_with_candidates(
        parse_result,
        meeting_note_text="用户可以留下信息，在订单完成后帮助用户完成修改，已经下单的商品不能再使用优惠券了。",
        llm_client=llm,
    )

    assert refined["budget_signals"] == ["不能再使用优惠券"]
    assert refined["timeline_signals"] == ["在订单完成后"]
    assert refined["next_steps"] == ["用户可以留下信息，在订单完成后帮助用户完成修改"]
