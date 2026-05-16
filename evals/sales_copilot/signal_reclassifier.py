from __future__ import annotations

import json
import re
from typing import Any

from sales_copilot.prompts import build_signal_reclassification_messages

TARGET_FIELDS = ("budget_signals", "timeline_signals", "next_steps")
_MAX_RECLASSIFICATION_ATTEMPTS = 2
_RECLASSIFICATION_TOOL_NAME = "classify_signal_candidates"
_TIME_MARKERS = (
    "今天",
    "明天",
    "之后",
    "完成后",
    "订单完成后",
    "工作日内",
    "within",
    "after",
    "tomorrow",
    "today",
)
_ACTION_MARKERS = (
    "联系",
    "申请",
    "修改",
    "留下信息",
    "重新下单",
    "寄回",
    "回电",
    "处理",
    "帮助",
    "回复",
    "provide",
    "contact",
    "apply",
    "modify",
    "reorder",
    "leave",
    "help",
    "reply",
)


def _count_marker_hits(text: str, markers: tuple[str, ...]) -> int:
    lowered = text.lower()
    hits = 0
    for marker in markers:
        if marker.isascii():
            hits += int(marker in lowered)
        else:
            hits += int(marker in text)
    return hits


def _detect_semantics(text: str) -> dict[str, int]:
    return {
        "timeline": _count_marker_hits(text, _TIME_MARKERS),
        "action": _count_marker_hits(text, _ACTION_MARKERS),
        "budget": _count_marker_hits(
            text,
            (
                "退款",
                "补偿",
                "优惠券",
                "差价",
                "返还",
                "价格",
                "费用",
                "refund",
                "coupon",
                "discount",
                "price",
                "compensation",
                "fee",
            ),
        ),
    }


def _rule_alignment_score(predicted_label: str, semantics: dict[str, int]) -> float:
    if predicted_label == "timeline_signals":
        return 0.25 if semantics["timeline"] > 0 else 0.0
    if predicted_label == "budget_signals":
        return 0.25 if semantics["budget"] > 0 else 0.0
    if predicted_label == "next_steps":
        return 0.25 if semantics["action"] > 0 else 0.0
    return 0.0


def _semantic_purity_score(semantics: dict[str, int]) -> float:
    active = sum(1 for value in semantics.values() if value > 0)
    if active == 1:
        return 0.20
    if active == 2:
        return 0.10
    return 0.0


def _completeness_score(text: str) -> float:
    length = len(text.strip())
    if length >= 8:
        return 0.15
    if length >= 4:
        return 0.03
    return 0.0


def _compute_confidence(predicted_label: str, text: str) -> tuple[float, str]:
    if predicted_label not in (*TARGET_FIELDS, "other"):
        return 0.0, "low"

    semantics = _detect_semantics(text)
    score = 0.30
    score += _rule_alignment_score(predicted_label, semantics)
    score += _semantic_purity_score(semantics)
    score += _completeness_score(text)

    if predicted_label == "next_steps" and semantics["timeline"] > 0 and semantics["action"] > 0:
        score = min(score, 0.70)

    if score >= 0.75:
        return score, "high"
    if score >= 0.45:
        return score, "medium"
    return score, "low"


def annotate_confidence(classified_signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    annotated: list[dict[str, Any]] = []
    for row in classified_signals:
        text = str(row.get("text", ""))
        predicted_label = str(row.get("predicted_label", "other"))
        score, level = _compute_confidence(predicted_label, text)
        annotated.append(
            {
                **row,
                "confidence_score": score,
                "confidence_level": level,
            }
        )
    return annotated


def merge_with_confidence(
    parse_result: dict[str, Any],
    classified_signals: list[dict[str, Any]],
) -> dict[str, Any]:
    merged = dict(parse_result)
    for field in TARGET_FIELDS:
        existing = merged.get(field, [])
        merged[field] = list(existing) if isinstance(existing, list) else []

    for row in classified_signals:
        text = row.get("text")
        if not isinstance(text, str) or not text.strip():
            continue

        level = str(row.get("confidence_level", "low"))
        labels = row.get("final_labels")
        if not isinstance(labels, list):
            predicted = row.get("predicted_label")
            labels = [predicted] if predicted in TARGET_FIELDS else []

        for label in labels:
            if label not in TARGET_FIELDS:
                continue
            if label == "next_steps" and _looks_time_like(text) and not _has_action_semantics(text):
                continue
            if text not in merged[label]:
                merged[label].append(text)

        if (
            level == "high"
            and row.get("predicted_label") == "timeline_signals"
            and _looks_time_like(text)
            and not _has_action_semantics(text)
        ):
            merged["next_steps"] = [value for value in merged["next_steps"] if value != text]

    return merged


def _extract_json_object_text(content: str) -> str:
    text = content.strip()
    if not text:
        raise ValueError("signal reclassification response is empty")

    fenced_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, flags=re.DOTALL)
    if fenced_match:
        return fenced_match.group(1)

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]

    raise ValueError("signal reclassification response does not contain a JSON object")


def _json_object(content: str) -> dict[str, Any]:
    last_error: Exception | None = None
    for candidate in (content, _extract_json_object_text(content)):
        try:
            payload = json.loads(candidate)
            if not isinstance(payload, dict):
                raise ValueError("signal reclassification response must be a JSON object")
            return payload
        except Exception as exc:  # noqa: BLE001 - keep parsing fallback simple
            last_error = exc
    raise ValueError("signal reclassification response is not valid JSON") from last_error


def extract_signal_candidates(parse_result: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    index = 1
    for field in (*TARGET_FIELDS, "objections"):
        values = parse_result.get(field, [])
        if not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, str) or not value.strip():
                continue
            text = value.strip()
            candidates.append(
                {
                    "candidate_id": f"sig_{index:03d}",
                    "text": text,
                    "speaker": "agent",
                    "evidence": text,
                    "normalized_text": text,
                    "hints": [],
                }
            )
            index += 1
    return candidates


def _request_classification_payload(
    candidates: list[dict[str, Any]],
    *,
    llm_client,
    conversation_context: str,
) -> dict[str, Any]:
    messages = build_signal_reclassification_messages(
        conversation_context=conversation_context,
        signal_candidates=[
            {
                "candidate_id": row["candidate_id"],
                "text": row["text"],
                "speaker": row.get("speaker", "agent"),
                "evidence": row.get("evidence", row["text"]),
            }
            for row in candidates
        ],
    )
    tool_schema = {
        "type": "function",
        "function": {
            "name": _RECLASSIFICATION_TOOL_NAME,
            "description": "Classify each signal candidate into one fixed label.",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "classifications": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "candidate_id": {"type": "string"},
                                "label": {
                                    "type": "string",
                                    "enum": ["budget_signals", "timeline_signals", "next_steps", "other"],
                                },
                            },
                            "required": ["candidate_id", "label"],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["classifications"],
                "additionalProperties": False,
            },
        },
    }
    tool_result = llm_client.complete_with_tool(
        messages,
        tools=[tool_schema],
        tool_choice={"type": "function", "function": {"name": _RECLASSIFICATION_TOOL_NAME}},
    )
    if tool_result.get("tool_name") != _RECLASSIFICATION_TOOL_NAME:
        raise ValueError("signal reclassification returned an unexpected tool")
    payload = tool_result.get("arguments")
    if not isinstance(payload, dict):
        raise ValueError("signal reclassification tool arguments must be a JSON object")
    classified = payload.get("classifications")
    if not isinstance(classified, list):
        raise ValueError("signal reclassification tool arguments are missing classifications")
    return payload


def reclassify_signal_candidates(
    candidates: list[dict[str, Any]],
    *,
    llm_client,
    conversation_context: str,
) -> list[dict[str, Any]]:
    if not candidates:
        return []

    last_error: Exception | None = None
    payload: dict[str, Any] | None = None
    for _ in range(_MAX_RECLASSIFICATION_ATTEMPTS):
        try:
            payload = _request_classification_payload(
                candidates,
                llm_client=llm_client,
                conversation_context=conversation_context,
            )
            break
        except Exception as exc:  # noqa: BLE001 - bounded retry around provider output
            last_error = exc
    if payload is None:
        raise ValueError("signal reclassification failed after retries") from last_error

    classified = payload["classifications"]
    candidate_by_id = {str(row["candidate_id"]): row for row in candidates}
    normalized: list[dict[str, Any]] = []
    for row in classified:
        if not isinstance(row, dict):
            continue
        candidate = candidate_by_id.get(str(row.get("candidate_id", "")))
        if candidate is None:
            continue
        alternative_labels = row.get("alternative_labels", [])
        normalized.append(
            {
                "candidate_id": candidate["candidate_id"],
                "text": candidate["text"],
                "predicted_label": str(row.get("label", "other")),
                "confidence": 1.0,
                "alternative_labels": list(alternative_labels) if isinstance(alternative_labels, list) else [],
                "notes": "",
            }
        )
    return normalized


def apply_signal_fallback(classified_signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    corrected: list[dict[str, Any]] = []
    for row in classified_signals:
        labels: list[str] = []
        predicted = row.get("predicted_label")
        if predicted in TARGET_FIELDS or predicted == "other":
            labels.append(str(predicted))

        text = str(row.get("text", ""))
        lowered = text.lower()
        confidence = float(row.get("confidence", 0.0))

        if confidence < 0.5 and any(
            token in text for token in ("工作日内", "今天", "明天", "之后", "完成后", "订单完成后")
        ):
            if "timeline_signals" not in labels:
                labels.append("timeline_signals")
        if confidence < 0.5 and any(
            token in text for token in ("退款", "补偿", "优惠券", "差价", "返还")
        ):
            if "budget_signals" not in labels:
                labels.append("budget_signals")
        if any(
            token in text for token in ("联系客服", "申请退款", "重新下单", "留下信息", "帮助用户", "修改")
        ) or any(
            token in lowered for token in ("contact support", "refund", "reorder", "leave contact", "modify", "after the order is completed")
        ):
            if "next_steps" not in labels:
                labels.append("next_steps")
        if confidence < 0.5 and any(
            token in lowered for token in ("after the order is completed", "after completion", "tomorrow", "today", "within")
        ):
            if "timeline_signals" not in labels:
                labels.append("timeline_signals")

        corrected.append({**row, "final_labels": labels})
    return corrected


def project_reclassified_parse_result(
    parse_result: dict[str, Any],
    classified_signals: list[dict[str, Any]],
) -> dict[str, Any]:
    projected = dict(parse_result)
    for field in TARGET_FIELDS:
        existing = projected.get(field, [])
        projected[field] = list(existing) if isinstance(existing, list) else []

    for row in classified_signals:
        text = row.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        for label in row.get("final_labels", []):
            if label == "next_steps" and _looks_time_like(text) and not _has_action_semantics(text):
                continue
            if label in TARGET_FIELDS and text not in projected[label]:
                projected[label].append(text)
    return projected


def reclassify_parse_result(
    parse_result: dict[str, Any],
    *,
    llm_client,
    source_note: str,
) -> dict[str, Any]:
    candidates = extract_signal_candidates(parse_result)
    classified = reclassify_signal_candidates(
        candidates,
        llm_client=llm_client,
        conversation_context=source_note,
    )
    corrected = apply_signal_fallback(classified)
    annotated = annotate_confidence(corrected)
    return merge_with_confidence(parse_result, annotated)


def _looks_time_like(text: str) -> bool:
    lowered = text.lower()
    return any(token in text for token in _TIME_MARKERS if not token.isascii()) or any(
        token in lowered for token in _TIME_MARKERS if token.isascii()
    )


def _has_action_semantics(text: str) -> bool:
    lowered = text.lower()
    return any(token in text for token in _ACTION_MARKERS if not token.isascii()) or any(
        token in lowered for token in _ACTION_MARKERS if token.isascii()
    )
