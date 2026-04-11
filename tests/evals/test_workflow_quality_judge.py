import pytest

from evals.sales_copilot.workflow_quality_judge import (
    build_stage1_messages,
    build_stage2_messages,
    build_stage1_tools,
    build_stage2_tools,
    parse_judge_result,
    WorkflowQualityJudge,
)


def test_build_stage1_messages_excludes_expected_workflow():
    messages = build_stage1_messages(
        case_id="case-1",
        meeting_note_text="Customer asked for proposal timeline.",
        actual_crm_writeback={"opportunity_stage": "qualification"},
        actual_generated_tasks=[{"title": "Send proposal"}],
    )

    joined = "\n".join(str(message["content"]) for message in messages)

    assert "expected_workflow" not in joined
    assert "actual_crm_writeback" in joined
    assert "actual_generated_tasks" in joined


def test_build_stage2_messages_includes_expected_workflow_and_stage1_result():
    messages = build_stage2_messages(
        case_id="case-1",
        meeting_note_text="Customer asked for proposal timeline.",
        actual_crm_writeback={"opportunity_stage": "qualification"},
        actual_generated_tasks=[{"title": "Send proposal"}],
        expected_workflow={"expected_crm_writeback": {"opportunity_stage": "proposal"}},
        stage1_result={"overall": {"overall_score": 4}},
    )

    joined = "\n".join(str(message["content"]) for message in messages)

    assert "expected_workflow" in joined
    assert "overall_score" in joined


def test_parse_judge_result_validates_required_scores():
    result = parse_judge_result(
        {
            "judge_result": {
                "crm_writeback": {
                    "field_correctness_score": 4,
                    "business_usability_score": 5,
                    "strengths": ["good stage"],
                    "issues": [],
                },
                "task_generation": {
                    "structure_correctness_score": 3,
                    "execution_quality_score": 4,
                    "strengths": ["actionable"],
                    "issues": [],
                },
                "overall": {
                    "overall_score": 4,
                    "verdict": "good",
                    "summary": "usable",
                },
                "benchmark_alignment": {
                    "alignment_score": 4,
                    "delta_note": "close to expected",
                },
            }
        }
    )

    assert result["judge_result"]["overall"]["overall_score"] == 4


def test_parse_judge_result_rejects_out_of_band_score():
    with pytest.raises(ValueError):
        parse_judge_result(
            {
                "judge_result": {
                    "crm_writeback": {
                        "field_correctness_score": 0,
                        "business_usability_score": 5,
                        "strengths": [],
                        "issues": [],
                    },
                    "task_generation": {
                        "structure_correctness_score": 3,
                        "execution_quality_score": 4,
                        "strengths": [],
                        "issues": [],
                    },
                    "overall": {
                        "overall_score": 4,
                        "verdict": "good",
                        "summary": "usable",
                    },
                    "benchmark_alignment": {
                        "alignment_score": 4,
                        "delta_note": "close to expected",
                    },
                }
            }
        )


def test_build_stage1_tools_exposes_score_bounds_and_verdict_enum():
    tools = build_stage1_tools()

    function = tools[0]["function"]
    judge_result = function["parameters"]["properties"]["crm_writeback"]["properties"]
    overall = function["parameters"]["properties"]["overall"]["properties"]

    assert function["strict"] is True
    assert judge_result["field_correctness_score"]["minimum"] == 1
    assert judge_result["field_correctness_score"]["maximum"] == 5
    assert overall["verdict"]["enum"] == ["poor", "acceptable", "good"]


def test_workflow_quality_judge_uses_tool_calls_for_both_stages():
    class FakeToolClient:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def complete_with_tool(self, messages, tools, tool_choice):
            self.calls.append(
                {
                    "messages": messages,
                    "tools": tools,
                    "tool_choice": tool_choice,
                }
            )
            if len(self.calls) == 1:
                return {
                    "tool_name": "submit_stage1_workflow_quality_review",
                    "arguments": {
                        "crm_writeback": {
                            "field_correctness_score": 4,
                            "business_usability_score": 4,
                            "strengths": ["clear stage"],
                            "issues": [],
                        },
                        "task_generation": {
                            "structure_correctness_score": 3,
                            "execution_quality_score": 4,
                            "strengths": ["actionable"],
                            "issues": [],
                        },
                        "overall": {
                            "overall_score": 4,
                            "verdict": "good",
                            "summary": "usable",
                        },
                    },
                }
            return {
                "tool_name": "submit_stage2_workflow_alignment_review",
                "arguments": {
                    "benchmark_alignment": {
                        "alignment_score": 4,
                        "delta_note": "close to expected",
                    }
                },
            }

    judge = WorkflowQualityJudge(FakeToolClient())

    stage1, stage2 = judge.evaluate_case(
        case_id="case-1",
        meeting_note_text="Customer asked for proposal timeline.",
        actual_crm_writeback={"opportunity_stage": "qualification"},
        actual_generated_tasks=[{"title": "Send proposal"}],
        expected_workflow={"expected_crm_writeback": {"opportunity_stage": "proposal"}},
    )

    assert stage1["crm_writeback"]["field_correctness_score"] == 4
    assert stage2["benchmark_alignment"]["alignment_score"] == 4


def test_workflow_quality_judge_retries_transient_tool_call_failure():
    class FlakyToolClient:
        def __init__(self) -> None:
            self.calls = 0

        def complete_with_tool(self, messages, tools, tool_choice):
            del messages, tools, tool_choice
            self.calls += 1
            if self.calls == 1:
                raise ValueError("DeepSeek response is missing tool_calls")
            if self.calls == 2:
                return {
                    "tool_name": "submit_stage1_workflow_quality_review",
                    "arguments": {
                        "crm_writeback": {
                            "field_correctness_score": 4,
                            "business_usability_score": 4,
                            "strengths": ["clear stage"],
                            "issues": [],
                        },
                        "task_generation": {
                            "structure_correctness_score": 3,
                            "execution_quality_score": 4,
                            "strengths": ["actionable"],
                            "issues": [],
                        },
                        "overall": {
                            "overall_score": 4,
                            "verdict": "good",
                            "summary": "usable",
                        },
                    },
                }
            return {
                "tool_name": "submit_stage2_workflow_alignment_review",
                "arguments": {
                    "benchmark_alignment": {
                        "alignment_score": 4,
                        "delta_note": "close to expected",
                    }
                },
            }

    judge = WorkflowQualityJudge(FlakyToolClient())

    stage1, stage2 = judge.evaluate_case(
        case_id="case-1",
        meeting_note_text="Customer asked for proposal timeline.",
        actual_crm_writeback={"opportunity_stage": "qualification"},
        actual_generated_tasks=[{"title": "Send proposal"}],
        expected_workflow={"expected_crm_writeback": {"opportunity_stage": "proposal"}},
    )

    assert stage1["overall"]["overall_score"] == 4
    assert stage2["benchmark_alignment"]["alignment_score"] == 4
