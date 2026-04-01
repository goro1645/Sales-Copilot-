from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from sales_copilot import storage


_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "sales_copilot"
_MEMORY_LIST_FIELDS = (
    "confirmed_needs_json",
    "budget_signals_json",
    "timeline_signals_json",
    "decision_makers_json",
    "risk_flags_json",
)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _json_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return [text]
        return _json_list(parsed)
    if isinstance(value, (list, tuple)):
        items: list[str] = []
        for item in value:
            if item is None:
                continue
            text = str(item).strip()
            if text:
                items.append(text)
        return items
    text = str(value).strip()
    return [text] if text else []


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _seed_rows_from_file(filename: str) -> list[dict]:
    data = _load_json(_DATA_DIR / filename)
    rows = data if isinstance(data, list) else data.get("chunks", [])
    normalized: list[dict] = []
    for row in rows:
        normalized.append(
            {
                "source_type": row.get("source_type", "product" if "product" in filename else "playbook"),
                "source_name": row["source_name"],
                "chunk_text": row["chunk_text"],
                "tags": list(row.get("tags", [])),
                "retrieval_metadata": dict(row.get("retrieval_metadata", {})),
            }
        )
    return normalized


def _row_tokens(row: dict) -> set[str]:
    parts: list[str] = []
    for key in ("chunk_text", "text", "title", "source_name", "description", "content"):
        value = row.get(key)
        if value:
            parts.append(str(value))
    tags = row.get("tags")
    if isinstance(tags, list):
        parts.extend(str(tag) for tag in tags if tag)
    tags_json = row.get("tags_json")
    if tags_json is not None:
        parts.extend(_json_list(tags_json))
    return set(tokenize(" ".join(parts)))


def tokenize(text: str) -> list[str]:
    # 只做最基础的词元化，避免把 public API 绑死在复杂归一化上。
    return re.findall(r"[a-z0-9]+", text.lower())


def ingest_text_file(path) -> dict:
    file_path = Path(path)
    text = _read_text(file_path)
    return {
        "filename": file_path.name,
        "source_path": str(file_path),
        "text": text,
    }


def keyword_retrieve(query: str, rows, top_k: int = 3) -> list[dict]:
    query_tokens = tokenize(query)
    query_set = set(query_tokens)
    ranked: list[dict] = []

    for index, row in enumerate(rows):
        row_tokens = _row_tokens(row)
        overlap = query_set & row_tokens
        phrase_hit = 1 if query and query.lower() in " ".join(
            str(row.get(key, "")) for key in ("chunk_text", "text", "title", "source_name", "description", "content")
        ).lower() else 0
        score = len(overlap) + phrase_hit
        ranked.append(
            {
                **row,
                "matched_terms": sorted(overlap),
                "score": score,
                "_row_index": index,
            }
        )

    ranked.sort(key=lambda item: (-item["score"], item["_row_index"]))
    for item in ranked:
        item.pop("_row_index", None)
    ranked = [item for item in ranked if item["score"] > 0]
    return ranked[: max(top_k, 0)]


def search_account_history(db_path, account_id: int) -> list[dict]:
    account = storage.get_account_by_id(db_path, account_id)
    if account is None:
        raise ValueError(f"Account {account_id} does not exist")

    meetings = [row for row in storage.list_meeting_records(db_path) if row["account_id"] == account_id]
    return meetings


def get_open_tasks(db_path, account_id: int) -> list[dict]:
    account = storage.get_account_by_id(db_path, account_id)
    if account is None:
        return []

    tasks = [row for row in storage.list_tasks(db_path) if row["account_id"] == account_id and row["status"] == "open"]
    return sorted(tasks, key=lambda row: (row["due_at"], row["id"]))


def _normalize_crm_after_payload(after: dict, *, meeting_id: int, before: dict) -> dict:
    normalized = {
        "meeting_id": meeting_id,
        "status": after.get("status", before["status"]),
        "opportunity_stage": after.get("opportunity_stage", before["opportunity_stage"]),
        "last_contact_at": after.get("last_contact_at", before.get("last_contact_at", "")),
    }
    for key, value in after.items():
        if key not in normalized:
            normalized[key] = value
    return normalized


def update_crm_account(db_path, account_id: int, after: dict) -> int:
    before = storage.get_account_by_id(db_path, account_id)
    if before is None:
        raise ValueError(f"Account {account_id} does not exist")

    meeting_id = after.get("meeting_id")
    if meeting_id is None:
        raise ValueError("after must include meeting_id")

    normalized_after = _normalize_crm_after_payload(after, meeting_id=meeting_id, before=before)

    with storage._connect(db_path) as conn:
        conn.row_factory = storage.sqlite3.Row
        meeting_row = conn.execute(
            "SELECT id, account_id FROM meeting_records WHERE id = ?",
            (meeting_id,),
        ).fetchone()
        if meeting_row is None:
            raise ValueError(f"Meeting {meeting_id} does not exist")
        if meeting_row["account_id"] != account_id:
            raise ValueError(f"Meeting {meeting_id} does not belong to account {account_id}")

        conn.execute(
            """
            UPDATE accounts
            SET status = ?, opportunity_stage = ?, last_contact_at = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                normalized_after["status"],
                normalized_after["opportunity_stage"],
                normalized_after["last_contact_at"],
                account_id,
            ),
        )
        payload = {
            "account_id": account_id,
            "meeting_id": meeting_id,
            "update_type": "account_state",
            "before_json": json.dumps(before, ensure_ascii=False),
            "after_json": json.dumps(normalized_after, ensure_ascii=False),
        }
        cursor = conn.execute(
            """
            INSERT INTO crm_updates (account_id, meeting_id, update_type, before_json, after_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                payload["account_id"],
                payload["meeting_id"],
                payload["update_type"],
                payload["before_json"],
                payload["after_json"],
            ),
        )
        return cursor.lastrowid


def _merge_json_field(existing: dict, incoming: dict, field: str) -> str:
    merged = _dedupe_preserve_order(_json_list(existing.get(field)) + _json_list(incoming.get(field)))
    return json.dumps(merged, ensure_ascii=False)


def merge_account_memory(existing: dict | None, incoming: dict) -> dict:
    existing = existing or {}
    merged = {
        field: _merge_json_field(existing, incoming, field)
        for field in _MEMORY_LIST_FIELDS
    }

    existing_next = str(existing.get("recommended_next_step", "") or "").strip()
    incoming_next = str(incoming.get("recommended_next_step", "") or "").strip()
    merged["recommended_next_step"] = incoming_next or existing_next
    return merged


def append_account_memory(db_path, account_id: int, memory_payload: dict) -> None:
    current = storage.get_account_memory(db_path, account_id)
    merged = merge_account_memory(current, memory_payload)
    storage.upsert_account_memory(db_path, account_id, merged)


def search_product_knowledge(db_path, query: str, top_k: int = 3) -> list[dict]:
    rows = storage.list_knowledge_chunks(db_path, source_type="product")
    return keyword_retrieve(query, rows, top_k=top_k)


def search_sales_playbook(db_path, query: str, top_k: int = 3) -> list[dict]:
    rows = storage.list_knowledge_chunks(db_path, source_type="playbook")
    return keyword_retrieve(query, rows, top_k=top_k)


def seed_knowledge_chunks(db_path, rows: list[dict]) -> None:
    existing = {
        (row["source_type"], row["source_name"], row["chunk_text"])
        for row in storage.list_knowledge_chunks(db_path)
    }
    for row in rows:
        key = (row["source_type"], row["source_name"], row["chunk_text"])
        if key in existing:
            continue
        storage.save_knowledge_chunk(
            db_path,
            {
                "source_type": row["source_type"],
                "source_name": row["source_name"],
                "chunk_text": row["chunk_text"],
                "tags_json": json.dumps(_dedupe_preserve_order(_json_list(row.get("tags"))), ensure_ascii=False),
                "retrieval_metadata_json": json.dumps(row.get("retrieval_metadata", {}), ensure_ascii=False),
            },
        )
        existing.add(key)


def sample_product_chunks() -> list[dict]:
    return _seed_rows_from_file("seed_product_knowledge.json")


def sample_playbook_chunks() -> list[dict]:
    return _seed_rows_from_file("seed_sales_playbook.json")
