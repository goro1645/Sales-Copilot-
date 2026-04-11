from __future__ import annotations

import json
from typing import Any


_STAGE1_SYSTEM_PROMPT = """You are evaluating the final quality of CRM writeback and generated tasks for a sales copilot workflow.
Judge business quality only from the original case context and actual output.
Do not compare to any benchmark or expected answer in this stage.
Return valid JSON only.
"""

_STAGE2_SYSTEM_PROMPT = """You are reviewing how closely an actual workflow output aligns with a benchmark draft.
Use the benchmark only to explain the delta after the independent business review already happened.
Do not rewrite the Stage 1 scores. Return valid JSON only.
"""

_VERDICTS = {"poor", "acceptable", "good"}
_STAGE1_TOOL_NAME = "submit_stage1_workflow_quality_review"
_STAGE2_TOOL_NAME = "submit_stage2_workflow_alignment_review"


def build_stage1_messages(
    *,
    case_id: str,
    meeting_note_text: str,
    actual_crm_writeback: dict[str, Any],
    actual_generated_tasks: list[dict[str, Any]],
    customer_profile_text: str = "",
) -> list[dict[str, str]]:
    payload = {
        "case_id": case_id,
        "meeting_note_text": meeting_note_text,
        "customer_profile_text": customer_profile_text,
        "actual_crm_writeback": actual_crm_writeback,
        "actual_generated_tasks": actual_generated_tasks,
        "rubric": {
            "crm_writeback": [
                "field_correctness_score",
                "business_usability_score",
            ],
            "task_generation": [
                "structure_correctness_score",
                "execution_quality_score",
            ],
            "overall": ["overall_score", "verdict", "summary"],
        },
    }
    return [
        {"role": "system", "content": _STAGE1_SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def build_stage2_messages(
    *,
    case_id: str,
    meeting_note_text: str,
    actual_crm_writeback: dict[str, Any],
    actual_generated_tasks: list[dict[str, Any]],
    expected_workflow: dict[str, Any],
    stage1_result: dict[str, Any],
    customer_profile_text: str = "",
) -> list[dict[str, str]]:
    payload = {
        "case_id": case_id,
        "meeting_note_text": meeting_note_text,
        "customer_profile_text": customer_profile_text,
        "actual_crm_writeback": actual_crm_writeback,
        "actual_generated_tasks": actual_generated_tasks,
        "expected_workflow": expected_workflow,
        "stage1_result": stage1_result,
        "rubric": {
            "benchmark_alignment": ["alignment_score", "delta_note"],
        },
    }
    return [
        {"role": "system", "content": _STAGE2_SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def _score_schema() -> dict[str, Any]:
    return {"type": "integer", "minimum": 1, "maximum": 5}


def build_stage1_tools() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": _STAGE1_TOOL_NAME,
                "description": "Submit the independent business-quality review for CRM writeback and generated tasks.",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "crm_writeback": {
                            "type": "object",
                            "properties": {
                                "field_correctness_score": _score_schema(),
                                "business_usability_score": _score_schema(),
                                "strengths": {"type": "array", "items": {"type": "string"}},
                                "issues": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": [
                                "field_correctness_score",
                                "business_usability_score",
                                "strengths",
                                "issues",
                            ],
                            "additionalProperties": False,
                        },
                        "task_generation": {
                            "type": "object",
                            "properties": {
                                "structure_correctness_score": _score_schema(),
                                "execution_quality_score": _score_schema(),
                                "strengths": {"type": "array", "items": {"type": "string"}},
                                "issues": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": [
                                "structure_correctness_score",
                                "execution_quality_score",
                                "strengths",
                                "issues",
                            ],
                            "additionalProperties": False,
                        },
                        "overall": {
                            "type": "object",
                            "properties": {
                                "overall_score": _score_schema(),
                                "verdict": {
                                    "type": "string",
                                    "enum": ["poor", "acceptable", "good"],
                                },
                                "summary": {"type": "string"},
                            },
                            "required": ["overall_score", "verdict", "summary"],
                            "additionalProperties": False,
                        },
                    },
                    "required": ["crm_writeback", "task_generation", "overall"],
                    "additionalProperties": False,
                },
            },
        }
    ]


def build_stage2_tools() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": _STAGE2_TOOL_NAME,
                "description": "Submit the benchmark alignment review for a workflow output.",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "benchmark_alignment": {
                            "type": "object",
                            "properties": {
                                "alignment_score": _score_schema(),
                                "delta_note": {"type": "string"},
                            },
                            "required": ["alignment_score", "delta_note"],
                            "additionalProperties": False,
                        }
                    },
                    "required": ["benchmark_alignment"],
                    "additionalProperties": False,
                },
            },
        }
    ]


def _ensure_score(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1 or value > 5:
        raise ValueError(f"{label} must be an integer from 1 to 5")
    return value


def _ensure_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def _ensure_string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list of strings")
    normalized: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{label}[{index}] must be a non-empty string")
        normalized.append(item.strip())
    return normalized


def parse_stage1_result(payload: dict[str, Any]) -> dict[str, Any]:
    crm = payload["crm_writeback"]
    task = payload["task_generation"]
    overall = payload["overall"]
    return {
        "crm_writeback": {
            "field_correctness_score": _ensure_score(crm["field_correctness_score"], "crm_writeback.field_correctness_score"),
            "business_usability_score": _ensure_score(crm["business_usability_score"], "crm_writeback.business_usability_score"),
            "strengths": _ensure_string_list(crm["strengths"], "crm_writeback.strengths"),
            "issues": _ensure_string_list(crm["issues"], "crm_writeback.issues"),
        },
        "task_generation": {
            "structure_correctness_score": _ensure_score(task["structure_correctness_score"], "task_generation.structure_correctness_score"),
            "execution_quality_score": _ensure_score(task["execution_quality_score"], "task_generation.execution_quality_score"),
            "strengths": _ensure_string_list(task["strengths"], "task_generation.strengths"),
            "issues": _ensure_string_list(task["issues"], "task_generation.issues"),
        },
        "overall": {
            "overall_score": _ensure_score(overall["overall_score"], "overall.overall_score"),
            "verdict": _ensure_verdict(overall["verdict"]),
            "summary": _ensure_string(overall["summary"], "overall.summary"),
        },
    }


def parse_stage2_alignment(payload: dict[str, Any]) -> dict[str, Any]:
    alignment = payload["benchmark_alignment"]
    return {
        "benchmark_alignment": {
            "alignment_score": _ensure_score(alignment["alignment_score"], "benchmark_alignment.alignment_score"),
            "delta_note": _ensure_string(alignment["delta_note"], "benchmark_alignment.delta_note"),
        }
    }


def _ensure_verdict(value: Any) -> str:
    verdict = _ensure_string(value, "overall.verdict")
    if verdict not in _VERDICTS:
        raise ValueError(f"overall.verdict must be one of {sorted(_VERDICTS)}")
    return verdict


def parse_judge_result(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("judge payload must be a dict")
    judge_result = payload.get("judge_result")
    if not isinstance(judge_result, dict):
        raise ValueError("judge_result must be an object")

    stage1 = parse_stage1_result(judge_result)
    stage2 = parse_stage2_alignment(judge_result)
    return {"judge_result": {**stage1, **stage2}}


class WorkflowQualityJudge:
    def __init__(self, llm_client, *, max_retries: int = 2) -> None:
        self._llm_client = llm_client
        self._max_retries = max_retries

    def evaluate_case(
        self,
        *,
        case_id: str,
        meeting_note_text: str,
        actual_crm_writeback: dict[str, Any],
        actual_generated_tasks: list[dict[str, Any]],
        expected_workflow: dict[str, Any],
        customer_profile_text: str = "",
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        stage1_messages = build_stage1_messages(
            case_id=case_id,
            meeting_note_text=meeting_note_text,
            actual_crm_writeback=actual_crm_writeback,
            actual_generated_tasks=actual_generated_tasks,
            customer_profile_text=customer_profile_text,
        )
        stage1_payload = self._complete_with_tool_retry(
            stage1_messages,
            build_stage1_tools(),
            {"type": "function", "function": {"name": _STAGE1_TOOL_NAME}},
        )
        stage1_result = parse_stage1_result(stage1_payload["arguments"])

        stage2_messages = build_stage2_messages(
            case_id=case_id,
            meeting_note_text=meeting_note_text,
            actual_crm_writeback=actual_crm_writeback,
            actual_generated_tasks=actual_generated_tasks,
            expected_workflow=expected_workflow,
            stage1_result=stage1_result,
            customer_profile_text=customer_profile_text,
        )
        stage2_payload = self._complete_with_tool_retry(
            stage2_messages,
            build_stage2_tools(),
            {"type": "function", "function": {"name": _STAGE2_TOOL_NAME}},
        )
        stage2_result = parse_stage2_alignment(stage2_payload["arguments"])
        return stage1_result, stage2_result

    def _complete_with_tool_retry(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        tool_choice: dict[str, Any],
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        for _ in range(self._max_retries + 1):
            try:
                return self._llm_client.complete_with_tool(messages, tools, tool_choice)
            except ValueError as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        raise RuntimeError("tool call retry exhausted without an error payload")
