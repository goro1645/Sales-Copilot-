from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, TypedDict, cast


class CSDSExpectedParse(TypedDict):
    account_name: str
    customer_roles: list[str]
    confirmed_needs: list[str]
    budget_signals: list[str]
    timeline_signals: list[str]
    next_steps: list[str]
    competitors: list[str]


class CSDSExpectedWorkflow(TypedDict):
    required_risk_flags: list[str]


class CSDSCase(TypedDict):
    case_id: str
    segment: str
    source_dataset: str
    source_uid: str
    source_split: str
    source_note: str
    customer_profile_text: str
    meeting_note_text: str
    expected_parse: CSDSExpectedParse
    expected_workflow: CSDSExpectedWorkflow


_TOP_LEVEL_FIELDS = (
    "case_id",
    "segment",
    "source_dataset",
    "source_uid",
    "source_split",
    "source_note",
    "customer_profile_text",
    "meeting_note_text",
    "expected_parse",
)
_EXPECTED_PARSE_FIELDS = (
    "account_name",
    "customer_roles",
    "confirmed_needs",
    "budget_signals",
    "timeline_signals",
    "next_steps",
    "competitors",
)
_FULL_CSDS_SPLITS = ("train", "val", "test")
_TIMELINE_PATTERNS = (
    r"\d+个工作日",
    r"\d+天",
    r"明天",
    r"今天",
    r"次日",
    r"审核后",
    r"到账",
    r"配送",
    r"送达",
)
_BUDGET_PATTERNS = (
    r"金额",
    r"优惠券",
    r"佣金",
    r"扣费",
    r"充值",
    r"税点",
    r"差价",
    r"余额",
)


def _ensure_object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _ensure_non_empty_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def _ensure_string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list of strings")
    result: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{label}[{index}] must be a non-empty string")
        result.append(item.strip())
    return result


def _normalize_case(payload: dict[str, object]) -> CSDSCase:
    missing_fields = [field for field in _TOP_LEVEL_FIELDS if field not in payload]
    if missing_fields:
        raise ValueError(f"csds case missing fields: {', '.join(missing_fields)}")

    expected_parse_payload = _ensure_object(payload["expected_parse"], "expected_parse")
    missing_parse_fields = [field for field in _EXPECTED_PARSE_FIELDS if field not in expected_parse_payload]
    if missing_parse_fields:
        raise ValueError(f"expected_parse missing fields: {', '.join(missing_parse_fields)}")

    expected_workflow_payload = payload.get("expected_workflow")
    if expected_workflow_payload is None:
        expected_workflow_payload = {"required_risk_flags": []}
    expected_workflow = _ensure_object(expected_workflow_payload, "expected_workflow")

    # CSDS 只接 parse-only 评测，这里仍保留 required_risk_flags 字段，
    # 这样可以直接复用现有 parse metrics 逻辑，不再额外分叉一套指标结构。
    normalized: CSDSCase = {
        "case_id": _ensure_non_empty_string(payload["case_id"], "case_id"),
        "segment": _ensure_non_empty_string(payload["segment"], "segment"),
        "source_dataset": _ensure_non_empty_string(payload["source_dataset"], "source_dataset"),
        "source_uid": _ensure_non_empty_string(payload["source_uid"], "source_uid"),
        "source_split": _ensure_non_empty_string(payload["source_split"], "source_split"),
        "source_note": _ensure_non_empty_string(payload["source_note"], "source_note"),
        "customer_profile_text": _ensure_non_empty_string(payload["customer_profile_text"], "customer_profile_text"),
        "meeting_note_text": _ensure_non_empty_string(payload["meeting_note_text"], "meeting_note_text"),
        "expected_parse": {
            "account_name": _ensure_non_empty_string(expected_parse_payload["account_name"], "expected_parse.account_name"),
            "customer_roles": _ensure_string_list(expected_parse_payload["customer_roles"], "expected_parse.customer_roles"),
            "confirmed_needs": _ensure_string_list(expected_parse_payload["confirmed_needs"], "expected_parse.confirmed_needs"),
            "budget_signals": _ensure_string_list(expected_parse_payload["budget_signals"], "expected_parse.budget_signals"),
            "timeline_signals": _ensure_string_list(expected_parse_payload["timeline_signals"], "expected_parse.timeline_signals"),
            "next_steps": _ensure_string_list(expected_parse_payload["next_steps"], "expected_parse.next_steps"),
            "competitors": _ensure_string_list(expected_parse_payload["competitors"], "expected_parse.competitors"),
        },
        "expected_workflow": {
            "required_risk_flags": _ensure_string_list(
                expected_workflow.get("required_risk_flags", []),
                "expected_workflow.required_risk_flags",
            )
        },
    }
    return normalized


def load_csds_cases(path: Path) -> list[CSDSCase]:
    cases: list[CSDSCase] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            if not isinstance(payload, dict):
                raise ValueError(f"line {line_number}: case must be a JSON object")
            try:
                cases.append(_normalize_case(payload))
            except ValueError as exc:
                raise ValueError(f"line {line_number}: {exc}") from exc
    return cast(list[CSDSCase], cases)


def _normalize_text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if text:
            items.append(text)
    return items


def _service_account_name(qrole: str) -> str:
    if "商家" in qrole:
        return "京东商家客服"
    if "物流" in qrole:
        return "京东物流客服"
    return "京东客服"


def _extract_signal_lines(lines: list[str], patterns: tuple[str, ...]) -> list[str]:
    result: list[str] = []
    for line in lines:
        if any(re.search(pattern, line) for pattern in patterns):
            result.append(line)
    return result


def _build_full_csds_case(payload: dict[str, Any], *, split: str) -> CSDSCase:
    dialogue_id = str(payload.get("DialogueID", "")).strip()
    if not dialogue_id:
        raise ValueError("DialogueID must be a non-empty value")
    qrole = _ensure_non_empty_string(payload.get("QRole", ""), "QRole")
    user_summ = _normalize_text_list(payload.get("UserSumm", []))
    agent_summ = _normalize_text_list(payload.get("AgentSumm", []))
    final_summ = _normalize_text_list(payload.get("FinalSumm", []))
    account_name = _service_account_name(qrole)
    return {
        "case_id": f"csds_full_{split}_{dialogue_id}",
        "segment": "customer_service_parse_only",
        "source_dataset": "CSDS",
        "source_uid": dialogue_id,
        "source_split": split,
        "source_note": "Official CSDS customer-service dialogue. Automatically adapted from UserSumm/AgentSumm/FinalSumm into parse-only evaluation input.",
        "customer_profile_text": (
            f"来源数据集：CSDS（公开真实中文客服对话语料）。账户名称：{account_name}。"
            f"会话角色：{qrole}、客服。场景：官方CSDS全量样本。"
        ),
        "meeting_note_text": f"账户：{account_name}\n会话摘要：\n" + "\n".join(f"- {line}" for line in final_summ),
        "expected_parse": {
            "account_name": account_name,
            "customer_roles": _dedupe_keep_order([qrole, "客服"]),
            "confirmed_needs": user_summ,
            "budget_signals": _extract_signal_lines(agent_summ, _BUDGET_PATTERNS),
            "timeline_signals": _extract_signal_lines(agent_summ, _TIMELINE_PATTERNS),
            "next_steps": agent_summ,
            "competitors": [],
        },
        "expected_workflow": {"required_risk_flags": []},
    }


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def load_full_csds_cases(dataset_dir: Path, *, splits: list[str] | None = None, limit: int | None = None) -> list[CSDSCase]:
    root = Path(dataset_dir)
    selected_splits = splits or list(_FULL_CSDS_SPLITS)
    for split in selected_splits:
        if split not in _FULL_CSDS_SPLITS:
            raise ValueError(f"unsupported CSDS split: {split}")
    if limit is not None and limit <= 0:
        raise ValueError("limit must be > 0")

    cases: list[CSDSCase] = []
    for split in selected_splits:
        split_path = root / f"{split}.json"
        if not split_path.exists():
            raise ValueError(f"missing CSDS split file: {split_path}")
        payload = json.loads(split_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"split file must contain a JSON list: {split_path}")
        for row in payload:
            if not isinstance(row, dict):
                raise ValueError(f"invalid CSDS row in {split_path}")
            cases.append(_build_full_csds_case(cast(dict[str, Any], row), split=split))
            if limit is not None and len(cases) >= limit:
                return cases
    return cases
