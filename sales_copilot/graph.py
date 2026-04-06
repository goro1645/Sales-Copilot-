from __future__ import annotations

import json
import re
from datetime import date, timedelta
from functools import partial
from pathlib import Path
from typing import Any, Callable

from langgraph.graph import END, StateGraph

from sales_copilot.prompts import (
    build_dashboard_summary_messages,
    build_followup_plan_messages,
    build_lead_scoring_messages,
    build_meeting_parse_messages,
)
from sales_copilot.state import SalesCopilotState
from sales_copilot.storage import (
    get_account_by_id,
    get_account_memory,
    list_accounts,
    list_crm_updates,
    list_meeting_records,
    list_tasks,
    save_account,
    save_meeting_record,
    save_task_record,
    update_meeting_record,
    update_task_record,
    upsert_account_memory,
)
from sales_copilot.tools import (
    append_account_memory,
    get_open_tasks,
    search_account_history,
    search_product_knowledge,
    search_sales_playbook,
    update_crm_account,
)


def _append_workflow_log(state: SalesCopilotState, step_name: str) -> dict[str, Any]:
    # 这里把节点执行顺序记下来，方便测试和排查流程跑到哪一步。
    workflow_log = list(state.get("workflow_log", []))
    workflow_log.append(step_name)
    return {"workflow_log": workflow_log}


def _step_result(state: SalesCopilotState, step_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    # 每个节点都沿用同一套日志更新方式，避免漏记流程痕迹。
    return {**payload, **_append_workflow_log(state, step_name)}


def _infer_account_name(customer_profile_raw: str) -> str:
    for line in customer_profile_raw.splitlines():
        cleaned = line.strip().lstrip("#").strip(" -*\t")
        if cleaned:
            lowered = cleaned.lower()
            for separator in (" is ", " are ", " was ", " were "):
                if separator in lowered:
                    candidate = cleaned[: lowered.index(separator)].strip(" ,.;:-")
                    if candidate:
                        return candidate
            return cleaned
    text = customer_profile_raw.strip()
    return text[:80] if text else "Unknown Account"


def _parse_json_object(content: str) -> dict[str, Any]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("LLM returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("LLM response must be a JSON object")
    return payload


def _coerce_lead_score(raw_lead_score: Any) -> int | None:
    try:
        return int(raw_lead_score)
    except (TypeError, ValueError):
        if isinstance(raw_lead_score, str):
            # 真实模型有时会返回 "84/100"、"score: 84" 这类字符串。
            # 这里提取第一个整数，尽量把稳定信号保留下来，而不是直接掉回 0 分。
            match = re.search(r"-?\d+", raw_lead_score)
            if match:
                return int(match.group(0))
        return None


def _normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _first_payload_value(payload: dict[str, Any], *keys: str) -> Any:
    # DeepSeek 偶尔会返回 score / priority / stage 这类别名。
    # 这里统一做兼容映射，避免模型轻微偏离 schema 时整条链路直接掉回 0 分兜底。
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return value
    return None


def _unwrap_payload_object(payload: dict[str, Any]) -> dict[str, Any]:
    # 一些模型会把真正结果再包一层，例如 {"result": {...}} 或 {"data": {...}}。
    # 这里做有限展开，只取最常见的容器键，避免把任意嵌套都当成业务结果。
    current = payload
    for _ in range(3):
        if any(key in current for key in ("lead_score", "score", "lead_priority", "priority", "opportunity_stage", "stage")):
            return current
        nested = None
        for key in ("result", "data", "output", "final", "response"):
            candidate = current.get(key)
            if isinstance(candidate, dict):
                nested = candidate
                break
        if nested is None:
            return current
        current = nested
    return current


def _build_follow_up_task(
    *,
    title: str,
    description: str,
    priority: str,
    due_in_days: int = 1,
) -> dict[str, Any]:
    # 统一补信息任务的结构，避免不同分支拼出来的字段不一致。
    normalized_priority = priority if priority in {"low", "medium", "high"} else "medium"
    return {
        "title": title,
        "description": description,
        "priority": normalized_priority,
        "due_at": (date.today() + timedelta(days=due_in_days)).isoformat(),
        "status": "open",
        "owner": "Sales",
    }


def _merge_task_payloads(*task_lists: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    # 同一轮工作流里，模型建议和补信息任务可能会同时产出。
    # 这里按标题 + 截止日期去重，避免一轮运行里把同一待办重复落库。
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for task_list in task_lists:
        for task in task_list or []:
            if not isinstance(task, dict):
                continue
            title = str(task.get("title", "Follow up")).strip() or "Follow up"
            due_at = str(task.get("due_at", date.today().isoformat())).strip() or date.today().isoformat()
            key = (title.lower(), due_at)
            if key in seen:
                continue
            seen.add(key)
            merged.append(
                {
                    "title": title,
                    "description": str(task.get("description", title)).strip() or title,
                    "priority": str(task.get("priority", "medium")).strip() or "medium",
                    "due_at": due_at,
                    "status": str(task.get("status", "open")).strip() or "open",
                    "owner": str(task.get("owner", "Sales")).strip() or "Sales",
                }
            )
    return merged


def _build_missing_fact_follow_up(state: SalesCopilotState) -> dict[str, Any]:
    # 这里把“信息不完整”翻译成销售可以执行的动作。
    # 这样工作台不会只会说“缺信息”，而是能直接落成待办任务。
    meeting_summary = state.get("meeting_summary") or {}
    priority = str(state.get("lead_priority", "medium") or "medium")
    missing_labels: list[str] = []
    tasks: list[dict[str, Any]] = []

    if not _normalize_list(meeting_summary.get("budget_signals")):
        missing_labels.append("预算")
        tasks.append(
            _build_follow_up_task(
                title="Confirm budget range",
                description="Clarify the pilot budget range, approval owner, and commercial path.",
                priority=priority,
                due_in_days=1,
            )
        )
    if not _normalize_list(meeting_summary.get("timeline_signals")):
        missing_labels.append("时间线")
        tasks.append(
            _build_follow_up_task(
                title="Confirm decision timeline",
                description="Confirm the target decision date, pilot start window, and review milestones.",
                priority=priority,
                due_in_days=1,
            )
        )
    if not _normalize_list(meeting_summary.get("customer_roles")):
        missing_labels.append("决策人")
        tasks.append(
            _build_follow_up_task(
                title="Identify decision makers",
                description="Identify the technical approver, business sponsor, and procurement stakeholders.",
                priority=priority,
                due_in_days=2,
            )
        )
    if not _normalize_list(meeting_summary.get("next_steps")):
        missing_labels.append("下一步动作")
        tasks.append(
            _build_follow_up_task(
                title="Schedule qualification follow-up",
                description="Book a follow-up meeting to close the remaining qualification gaps.",
                priority=priority,
                due_in_days=2,
            )
        )

    if not tasks:
        tasks.append(
            _build_follow_up_task(
                title="Clarify qualification gaps",
                description="Review the remaining qualification gaps and align the next customer touchpoint.",
                priority=priority,
                due_in_days=1,
            )
        )

    summary = f"补齐{'、'.join(missing_labels)}等关键信息，并安排下一次跟进。" if missing_labels else "补齐剩余资格信息，并安排下一次跟进。"
    return {"summary": summary, "tasks": tasks}


def _augment_follow_up_payload_with_missing_facts(
    state: SalesCopilotState,
    payload: dict[str, Any],
) -> dict[str, Any]:
    # missing_required_facts 现在是风险信号，而不是流程终止条件。
    # 这里把风险补成明确任务，保证 CRM 和任务看板里能看到“接下来要补什么”。
    risk_flags = set(_normalize_list(state.get("risk_flags")))
    if "missing_required_facts" not in risk_flags:
        payload["tasks"] = _merge_task_payloads(payload.get("tasks", []))
        return payload

    supplement = _build_missing_fact_follow_up(state)
    payload["tasks"] = _merge_task_payloads(payload.get("tasks", []), supplement["tasks"])
    existing_summary = str(payload.get("summary", "")).strip()
    payload["summary"] = f"{existing_summary} 同时，{supplement['summary']}" if existing_summary else supplement["summary"]
    return payload


def _looks_generic_account_name(value: str) -> bool:
    text = value.strip().lower()
    if not text:
        return True
    if text.endswith("."):
        return True
    generic_markers = ("customer profile", "profile", "customer", "company", "business", "account", "client")
    if any(marker in text for marker in generic_markers):
        # 这里只拦很明显的占位文本，避免把真实公司名误判得太狠。
        return True
    return False


def _get_or_create_account(db_path: Path | str, *, account_name: str) -> int:
    normalized_name = account_name.strip().lower()
    # 先复用同名账号，避免重复运行时把同一个客户建成多条记录。
    for account in list_accounts(db_path):
        if account["name"].strip().lower() == normalized_name:
            return account["id"]

    return save_account(
        db_path,
        {
            "name": account_name,
            "industry": "Unknown",
            "size_segment": "Unknown",
            "status": "active",
            "opportunity_stage": "discovery",
        },
    )


def _resolve_account_name(
    state: SalesCopilotState,
    *,
    database_path: Path | str | None = None,
) -> str:
    # 先读已经落库的账号名，能避免同一条线索在 UI 里被“简介句子”误当成名称。
    account_id = state.get("account_id")
    if database_path is not None and account_id:
        account = get_account_by_id(database_path, account_id)
        if account and account.get("name"):
            return str(account["name"])

    structured_name = str((state.get("customer_profile_structured") or {}).get("account_name", "")).strip()
    if structured_name and not _looks_generic_account_name(structured_name):
        return structured_name

    summary_name = str((state.get("meeting_summary") or {}).get("account_name", "")).strip()
    if summary_name:
        return summary_name

    if structured_name:
        return structured_name

    return _infer_account_name(state.get("customer_profile_raw", ""))


def _find_existing_meeting(db_path: Path | str, *, account_id: int, meeting_note_raw: str) -> int | None:
    for row in list_meeting_records(db_path):
        if row["account_id"] == account_id and row["meeting_note_raw"] == meeting_note_raw:
            return row["id"]
    return None


def _find_existing_task(
    db_path: Path | str,
    *,
    account_id: int,
    meeting_id: int,
    title: str,
) -> int | None:
    for row in list_tasks(db_path):
        if (
            row["account_id"] == account_id
            and row["meeting_id"] == meeting_id
            and row["title"] == title
            and row["status"] == "open"
        ):
            return row["id"]
    return None


def _find_existing_crm_update(
    db_path: Path | str,
    *,
    account_id: int,
    meeting_id: int,
    after_json: str,
) -> int | None:
    for row in list_crm_updates(db_path):
        if row["account_id"] == account_id and row["meeting_id"] == meeting_id and row["after_json"] == after_json:
            return row["id"]
    return None


def ingest_files_node(state: SalesCopilotState, *, llm_client=None, database_path=None) -> dict[str, Any]:
    del llm_client, database_path
    customer_profile_raw = state.get("customer_profile_raw", "")
    account_name = _infer_account_name(customer_profile_raw)
    customer_profile_structured = dict(state.get("customer_profile_structured", {}))
    customer_profile_structured.setdefault("account_name", account_name)
    return _step_result(state, "ingest_files", {"customer_profile_structured": customer_profile_structured})


def parse_meeting_note_node(state: SalesCopilotState, *, llm_client, database_path=None) -> dict[str, Any]:
    del database_path
    existing_summary = state.get("meeting_summary")
    # Allow pre-seeded summaries in tests and callers to flow through unchanged.
    if state.get("meeting_summary_provided") or (
        isinstance(existing_summary, dict) and existing_summary and not state.get("meeting_note_raw")
    ):
        return _step_result(state, "parse_meeting_note", {"meeting_summary": existing_summary})
    messages = build_meeting_parse_messages(
        customer_profile_text=state.get("customer_profile_raw", ""),
        meeting_note_text=state.get("meeting_note_raw", ""),
    )
    content = llm_client.complete(messages, response_format={"type": "json_object"})
    payload = _parse_json_object(content)
    return _step_result(state, "parse_meeting_note", {"meeting_summary": payload})


def retrieve_context_node(state: SalesCopilotState, *, llm_client=None, database_path=None) -> dict[str, Any]:
    del llm_client
    query_bits = _normalize_list((state.get("meeting_summary") or {}).get("confirmed_needs"))
    query = " ".join(query_bits).strip() or state.get("meeting_note_raw", "")
    docs: list[dict[str, Any]] = []
    if database_path is not None and query:
        docs.extend(search_product_knowledge(database_path, query, top_k=2))
        docs.extend(search_sales_playbook(database_path, query, top_k=2))
    account_id = state.get("account_id")
    if database_path is not None and account_id:
        docs.extend(search_account_history(database_path, account_id)[:2])
    return _step_result(state, "retrieve_context", {"retrieved_docs": docs})


def load_account_memory_node(state: SalesCopilotState, *, llm_client=None, database_path=None) -> dict[str, Any]:
    del llm_client
    account_id = state.get("account_id")
    if not account_id or database_path is None:
        return _step_result(state, "load_account_memory", {"account_memory": {}, "open_tasks": []})

    memory = get_account_memory(database_path, account_id) or {}
    tasks = get_open_tasks(database_path, account_id)
    return _step_result(state, "load_account_memory", {"account_memory": memory, "open_tasks": tasks})


def evaluate_lead_node(state: SalesCopilotState, *, llm_client, database_path=None) -> dict[str, Any]:
    del database_path
    if (
        state.get("lead_score") is not None
        and not state.get("customer_profile_raw")
        and not state.get("meeting_note_raw")
        and state.get("meeting_summary")
    ):
        return _step_result(
            state,
            "evaluate_lead",
            {
                "lead_score": state.get("lead_score", 0),
                "lead_priority": state.get("lead_priority", "medium"),
                "opportunity_stage": state.get("opportunity_stage", "discovery"),
                "risk_flags": list(state.get("risk_flags", [])),
            },
        )
    messages = build_lead_scoring_messages(
        customer_profile_text=state.get("customer_profile_raw", ""),
        meeting_summary=state.get("meeting_summary", {}),
        retrieved_docs=state.get("retrieved_docs", []),
        account_memory=state.get("account_memory", {}),
    )
    payload = _unwrap_payload_object(
        _parse_json_object(llm_client.complete(messages, response_format={"type": "json_object"}))
    )
    lead_score = _coerce_lead_score(_first_payload_value(payload, "lead_score", "score"))
    lead_priority = str(
        _first_payload_value(payload, "lead_priority", "priority")
        or ("high" if lead_score and lead_score >= 80 else "medium")
    )
    opportunity_stage = str(_first_payload_value(payload, "opportunity_stage", "stage") or "discovery")
    risk_flags = _normalize_list(_first_payload_value(payload, "risk_flags", "risks", "risk_labels"))
    return _step_result(
        state,
        "evaluate_lead",
        {
            "lead_score": lead_score if lead_score is not None else 0,
            "lead_priority": lead_priority,
            "opportunity_stage": opportunity_stage,
            "risk_flags": risk_flags,
        },
    )


def need_more_info_node(state: SalesCopilotState, *, llm_client=None, database_path=None) -> dict[str, Any]:
    del llm_client, database_path
    follow_up_plan = _build_missing_fact_follow_up(state)
    return _step_result(
        state,
        "need_more_info",
        {"follow_up_plan": follow_up_plan, "task_payload": list(follow_up_plan.get("tasks", []))},
    )


def low_priority_nurture_node(state: SalesCopilotState, *, llm_client=None, database_path=None) -> dict[str, Any]:
    del llm_client, database_path
    follow_up_plan = {
        "summary": "放入低优先级培育流程，先推送轻量教育内容。",
        "tasks": [],
    }
    follow_up_plan = _augment_follow_up_payload_with_missing_facts(state, follow_up_plan)
    return _step_result(
        state,
        "low_priority_nurture",
        {"follow_up_plan": follow_up_plan, "task_payload": list(follow_up_plan.get("tasks", []))},
    )


def _build_followup_payload(state: SalesCopilotState, *, llm_client) -> dict[str, Any]:
    messages = build_followup_plan_messages(
        meeting_summary=state.get("meeting_summary", {}),
        opportunity_stage=state.get("opportunity_stage", ""),
        risk_flags=_normalize_list(state.get("risk_flags")),
    )
    payload = _parse_json_object(llm_client.complete(messages, response_format={"type": "json_object"}))
    tasks = payload.get("tasks") or payload.get("task_payload") or []
    payload["tasks"] = tasks if isinstance(tasks, list) else []
    return _augment_follow_up_payload_with_missing_facts(state, payload)


def standard_follow_up_node(state: SalesCopilotState, *, llm_client, database_path=None) -> dict[str, Any]:
    del database_path
    payload = _build_followup_payload(state, llm_client=llm_client)
    return _step_result(state, "standard_follow_up", {"follow_up_plan": payload, "task_payload": list(payload.get("tasks", []))})


def high_priority_follow_up_node(state: SalesCopilotState, *, llm_client, database_path=None) -> dict[str, Any]:
    del database_path
    payload = _build_followup_payload(state, llm_client=llm_client)
    return _step_result(state, "high_priority_follow_up", {"follow_up_plan": payload, "task_payload": list(payload.get("tasks", []))})


def write_back_crm_node(state: SalesCopilotState, *, llm_client=None, database_path=None) -> dict[str, Any]:
    del llm_client
    if database_path is None:
        return _step_result(state, "write_back_crm", {"crm_update_ids": []})

    account_name = _resolve_account_name(state, database_path=database_path)
    account_id = state.get("account_id")
    if account_id:
        account = get_account_by_id(database_path, account_id)
        if account is None:
            raise ValueError(f"Account {account_id} does not exist")
    else:
        account_id = _get_or_create_account(database_path, account_name=account_name)

    meeting_summary = state.get("meeting_summary", {})
    meeting_id = state.get("meeting_id")
    meeting_title = meeting_summary.get("account_name") or f"{account_name} meeting"
    meeting_reused = bool(meeting_id)
    if not meeting_id:
        meeting_note_raw = state.get("meeting_note_raw", "")
        existing_meeting_id = _find_existing_meeting(database_path, account_id=account_id, meeting_note_raw=meeting_note_raw)
        if existing_meeting_id is not None:
            meeting_id = existing_meeting_id
            meeting_reused = True
            update_meeting_record(
                database_path,
                meeting_id=meeting_id,
                record={
                    "meeting_title": meeting_title,
                    "meeting_summary_json": json.dumps(meeting_summary, ensure_ascii=False),
                    "lead_score": state.get("lead_score", 0),
                    "priority": state.get("lead_priority", "medium"),
                },
            )
        else:
            meeting_id = save_meeting_record(
                database_path,
                {
                    "account_id": account_id,
                    "meeting_title": meeting_title,
                    "meeting_note_raw": meeting_note_raw,
                    "meeting_summary_json": json.dumps(meeting_summary, ensure_ascii=False),
                    "lead_score": state.get("lead_score", 0),
                    "priority": state.get("lead_priority", "medium"),
                },
            )

    task_payload = state.get("task_payload", [])
    task_ids: list[int] = []
    for task in task_payload:
        if not isinstance(task, dict):
            continue
        title = str(task.get("title", "Follow up"))
        due_at = str(task.get("due_at", date.today().isoformat()))
        existing_task_id = _find_existing_task(
            database_path,
            account_id=account_id,
            meeting_id=meeting_id,
            title=title,
        )
        if existing_task_id is not None:
            update_task_record(
                database_path,
                task_id=existing_task_id,
                record={
                    "description": task.get("description", title),
                    "priority": task.get("priority", state.get("lead_priority", "medium")),
                    "due_at": due_at,
                    "status": task.get("status", "open"),
                },
            )
            task_ids.append(existing_task_id)
            continue
        task_ids.append(
            save_task_record(
                database_path,
                {
                    "account_id": account_id,
                    "meeting_id": meeting_id,
                    "title": title,
                    "description": task.get("description", title),
                    "priority": task.get("priority", state.get("lead_priority", "medium")),
                    "due_at": due_at,
                    "status": task.get("status", "open"),
                },
            )
        )

    crm_after = {
        "meeting_id": meeting_id,
        "status": "active",
        "opportunity_stage": state.get("opportunity_stage", "discovery"),
        "last_contact_at": date.today().isoformat(),
    }
    crm_after_json = json.dumps(crm_after, ensure_ascii=False)
    existing_crm_update_id = _find_existing_crm_update(
        database_path,
        account_id=account_id,
        meeting_id=meeting_id,
        after_json=crm_after_json,
    )
    if existing_crm_update_id is not None:
        crm_update_id = existing_crm_update_id
    else:
        crm_update_id = update_crm_account(
            database_path,
            account_id,
            crm_after,
        )

    memory_payload = {
        "confirmed_needs_json": json.dumps(_normalize_list(meeting_summary.get("confirmed_needs")), ensure_ascii=False),
        "budget_signals_json": json.dumps(_normalize_list(meeting_summary.get("budget_signals")), ensure_ascii=False),
        "timeline_signals_json": json.dumps(_normalize_list(meeting_summary.get("timeline_signals")), ensure_ascii=False),
        "decision_makers_json": json.dumps(_normalize_list(meeting_summary.get("customer_roles")), ensure_ascii=False),
        "risk_flags_json": json.dumps(_normalize_list(state.get("risk_flags")), ensure_ascii=False),
        "recommended_next_step": str((state.get("follow_up_plan") or {}).get("summary", "")).strip(),
    }
    if meeting_reused:
        upsert_account_memory(database_path, account_id, memory_payload)
    else:
        append_account_memory(database_path, account_id, memory_payload)

    return _step_result(
        state,
        "write_back_crm",
        {
            "account_id": account_id,
            "meeting_id": meeting_id,
            "crm_update_ids": [crm_update_id],
            "task_payload": task_payload,
            "task_ids": task_ids,
        },
    )


def generate_dashboard_output_node(state: SalesCopilotState, *, llm_client=None, database_path=None) -> dict[str, Any]:
    del llm_client
    account_name = _resolve_account_name(state, database_path=database_path)
    follow_up_plan = state.get("follow_up_plan", {})
    dashboard_messages = build_dashboard_summary_messages(
        meeting_parse_json=json.dumps(state.get("meeting_summary", {}), ensure_ascii=False),
        lead_scoring_json=json.dumps(
            {
                "lead_score": state.get("lead_score", 0),
                "lead_priority": state.get("lead_priority", "unknown"),
                "opportunity_stage": state.get("opportunity_stage", ""),
                "risk_flags": state.get("risk_flags", []),
            },
            ensure_ascii=False,
        ),
        followup_plan_json=json.dumps(follow_up_plan, ensure_ascii=False),
        crm_update_json=json.dumps(
            {
                "crm_update_ids": state.get("crm_update_ids", []),
                "meeting_id": state.get("meeting_id"),
                "account_id": state.get("account_id"),
            },
            ensure_ascii=False,
        )
        if state.get("crm_update_ids")
        else None,
    )
    dashboard_output = {
        "account_name": account_name,
        "lead_score": state.get("lead_score", 0),
        "lead_priority": state.get("lead_priority", "unknown"),
        "opportunity_stage": state.get("opportunity_stage", ""),
        "summary": str(follow_up_plan.get("summary", "")).strip(),
        "crm_update_ids": list(state.get("crm_update_ids") or []),
        "retrieved_doc_count": len(state.get("retrieved_docs", [])),
        "messages": dashboard_messages,
    }
    return _step_result(
        state,
        "generate_dashboard_output",
        {
            "dashboard_output": dashboard_output,
            "crm_update_ids": list(state.get("crm_update_ids") or []),
        },
    )


def route_after_lead_evaluation(state: SalesCopilotState) -> str:
    meeting_summary = state.get("meeting_summary") or {}
    lead_score = _coerce_lead_score(state.get("lead_score", 0))

    # 只有在会议摘要不可用，或者模型没有给出可解析分数时，才退回补信息分支。
    # 像 missing_required_facts 这样的标签现在只表示风险，不再直接掐断后续跟进。
    if not meeting_summary or lead_score is None:
        return "need_more_info"
    if lead_score < 50:
        return "low_priority_nurture"
    if lead_score < 80:
        return "standard_follow_up"
    return "high_priority_follow_up"


def _bind_node(node: Callable[..., dict[str, Any]], *, llm_client=None, database_path=None) -> Callable[[SalesCopilotState], dict[str, Any]]:
    return partial(node, llm_client=llm_client, database_path=database_path)


def build_sales_copilot_graph(*, llm_client, database_path) -> Any:
    builder = StateGraph(SalesCopilotState)

    builder.add_node("ingest_files", _bind_node(ingest_files_node, llm_client=llm_client, database_path=database_path))
    builder.add_node("parse_meeting_note", _bind_node(parse_meeting_note_node, llm_client=llm_client, database_path=database_path))
    builder.add_node("retrieve_context", _bind_node(retrieve_context_node, llm_client=llm_client, database_path=database_path))
    builder.add_node("load_account_memory", _bind_node(load_account_memory_node, llm_client=llm_client, database_path=database_path))
    builder.add_node("evaluate_lead", _bind_node(evaluate_lead_node, llm_client=llm_client, database_path=database_path))
    builder.add_node("need_more_info", _bind_node(need_more_info_node, llm_client=llm_client, database_path=database_path))
    builder.add_node("low_priority_nurture", _bind_node(low_priority_nurture_node, llm_client=llm_client, database_path=database_path))
    builder.add_node("standard_follow_up", _bind_node(standard_follow_up_node, llm_client=llm_client, database_path=database_path))
    builder.add_node("high_priority_follow_up", _bind_node(high_priority_follow_up_node, llm_client=llm_client, database_path=database_path))
    builder.add_node("write_back_crm", _bind_node(write_back_crm_node, llm_client=llm_client, database_path=database_path))
    builder.add_node("generate_dashboard_output", _bind_node(generate_dashboard_output_node, llm_client=llm_client, database_path=database_path))

    builder.set_entry_point("ingest_files")
    builder.add_edge("ingest_files", "parse_meeting_note")
    builder.add_edge("parse_meeting_note", "retrieve_context")
    builder.add_edge("retrieve_context", "load_account_memory")
    builder.add_edge("load_account_memory", "evaluate_lead")

    builder.add_conditional_edges(
        "evaluate_lead",
        route_after_lead_evaluation,
        {
            "need_more_info": "need_more_info",
            "low_priority_nurture": "low_priority_nurture",
            "standard_follow_up": "standard_follow_up",
            "high_priority_follow_up": "high_priority_follow_up",
        },
    )

    builder.add_edge("need_more_info", "write_back_crm")
    builder.add_edge("low_priority_nurture", "write_back_crm")
    builder.add_edge("standard_follow_up", "write_back_crm")
    builder.add_edge("high_priority_follow_up", "write_back_crm")
    builder.add_edge("write_back_crm", "generate_dashboard_output")
    builder.add_edge("generate_dashboard_output", END)

    return builder.compile()
