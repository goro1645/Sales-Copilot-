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


def _read_json_file(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _parse_json_text(value: Any) -> Any:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return value


def _normalize_items(value: Any) -> list[str]:
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
        return _normalize_items(parsed)
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


def _chunk_text(text: str) -> list[str]:
    # 先按空行切块，够稳定，也方便后续检索。
    chunks = [part.strip() for part in re.split(r"\n\s*\n+", text.strip()) if part.strip()]
    return chunks or ([text.strip()] if text.strip() else [])


def _seed_file_path(filename: str) -> Path:
    return _DATA_DIR / filename


def _load_seed_chunks(filename: str) -> list[dict]:
    data = _read_json_file(_seed_file_path(filename))
    chunks = data.get("chunks", [])
    return [
        {
            "source_type": data["source_type"],
            "source_name": data["source_name"],
            "chunk_text": chunk["chunk_text"],
            "tags": list(chunk.get("tags", [])),
            "retrieval_metadata": dict(chunk.get("retrieval_metadata", {})),
        }
        for chunk in chunks
    ]


def tokenize(text: str) -> list[str]:
    # 用最朴素的分词就够了，避免引入复杂归一化。
    return re.findall(r"[a-z0-9]+", text.lower())


def ingest_text_file(
    db_path,
    file_path,
    *,
    source_type: str,
    source_name: str | None = None,
    tags: list[str] | None = None,
) -> list[dict]:
    path = Path(file_path)
    text = path.read_text(encoding="utf-8")
    chunk_list = _chunk_text(text)
    saved_chunks: list[dict] = []
    effective_source_name = source_name or path.stem
    base_tags = _dedupe_preserve_order((tags or []) + [source_type, effective_source_name])

    for index, chunk_text in enumerate(chunk_list, start=1):
        payload = {
            "source_type": source_type,
            "source_name": effective_source_name,
            "chunk_text": chunk_text,
            "tags_json": json.dumps(base_tags, ensure_ascii=False),
            "retrieval_metadata_json": json.dumps(
                {
                    "source_path": str(path),
                    "chunk_index": index,
                    "chunk_count": len(chunk_list),
                },
                ensure_ascii=False,
            ),
        }
        chunk_id = storage.save_knowledge_chunk(db_path, payload)
        saved_chunks.append(
            {
                "id": chunk_id,
                "source_type": source_type,
                "source_name": effective_source_name,
                "chunk_text": chunk_text,
                "tags": list(base_tags),
            }
        )
    return saved_chunks


def keyword_retrieve(db_path, query: str, *, source_type: str | None = None, limit: int = 5) -> list[dict]:
    query_tokens = set(tokenize(query))
    rows = storage.list_knowledge_chunks(db_path, source_type=source_type)
    ranked: list[dict] = []

    for row in rows:
        chunk_tokens = set(tokenize(row["chunk_text"]))
        tags = _normalize_items(row["tags_json"])
        tag_tokens = set(tokenize(" ".join(tags)))
        matched = sorted(query_tokens & (chunk_tokens | tag_tokens))
        score = len(query_tokens & chunk_tokens) + (len(query_tokens & tag_tokens) * 2)
        if query and query.lower() in row["chunk_text"].lower():
            score += 1
        ranked.append(
            {
                **row,
                "tags": tags,
                "retrieval_metadata": _parse_json_text(row["retrieval_metadata_json"]),
                "matched_terms": matched,
                "score": score,
            }
        )

    ranked.sort(key=lambda item: (-item["score"], item["id"]))
    if limit <= 0:
        return []
    return ranked[:limit]


def _find_account_by_name(db_path, account_name: str) -> dict | None:
    target = account_name.strip().lower()
    rows = storage.list_accounts(db_path)
    exact_matches = [row for row in rows if row["name"].strip().lower() == target]
    if exact_matches:
        return exact_matches[0]
    partial_matches = [row for row in rows if target in row["name"].strip().lower()]
    return partial_matches[0] if partial_matches else None


def search_account_history(db_path, account_name: str) -> dict:
    account = _find_account_by_name(db_path, account_name)
    if account is None:
        raise ValueError(f"Account not found: {account_name}")

    account_id = account["id"]
    meetings = [row for row in storage.list_meeting_records(db_path) if row["account_id"] == account_id]
    tasks = [row for row in storage.list_tasks(db_path) if row["account_id"] == account_id]
    crm_updates = [row for row in storage.list_crm_updates(db_path) if row["account_id"] == account_id]
    memory = storage.get_account_memory(db_path, account_id)

    return {
        "account": account,
        "meetings": meetings,
        "tasks": tasks,
        "crm_updates": crm_updates,
        "memory": memory,
    }


def get_open_tasks(db_path, account_name: str | None = None) -> list[dict]:
    account_id: int | None = None
    if account_name is not None:
        account = _find_account_by_name(db_path, account_name)
        if account is None:
            return []
        account_id = account["id"]

    rows = storage.list_tasks(db_path)
    filtered = [row for row in rows if row["status"] == "open"]
    if account_id is not None:
        filtered = [row for row in filtered if row["account_id"] == account_id]
    return sorted(filtered, key=lambda row: (row["due_at"], row["id"]))


def update_crm_account(
    db_path,
    *,
    account_id: int,
    meeting_id: int,
    status: str,
    opportunity_stage: str,
    last_contact_at: str,
) -> dict:
    before = storage.get_account_by_id(db_path, account_id)
    if before is None:
        raise ValueError(f"Account {account_id} does not exist")

    storage.update_account_stage_and_status(
        db_path,
        account_id=account_id,
        status=status,
        opportunity_stage=opportunity_stage,
        last_contact_at=last_contact_at,
    )
    after = storage.get_account_by_id(db_path, account_id)
    if after is None:
        raise ValueError(f"Account {account_id} disappeared during update")

    update_id = storage.save_crm_update(
        db_path,
        {
            "account_id": account_id,
            "meeting_id": meeting_id,
            "update_type": "account_stage",
            "before_json": json.dumps(before, ensure_ascii=False),
            "after_json": json.dumps(after, ensure_ascii=False),
        },
    )
    return {"update_id": update_id, "before": before, "after": after}


def merge_account_memory(existing: dict | None, incoming: dict) -> dict:
    merged: dict[str, Any] = {}
    existing = existing or {}

    for field in _MEMORY_LIST_FIELDS:
        combined = _normalize_items(existing.get(field)) + _normalize_items(incoming.get(field))
        merged[field] = json.dumps(_dedupe_preserve_order(combined), ensure_ascii=False)

    existing_next = str(existing.get("recommended_next_step", "") or "").strip()
    incoming_next = str(incoming.get("recommended_next_step", "") or "").strip()
    merged["recommended_next_step"] = incoming_next or existing_next
    return merged


def append_account_memory(db_path, *, account_id: int, payload: dict) -> dict:
    current = storage.get_account_memory(db_path, account_id)
    merged = merge_account_memory(current, payload)
    storage.upsert_account_memory(db_path, account_id, merged)
    return merged


def search_product_knowledge(db_path, query: str, *, limit: int = 5) -> list[dict]:
    return keyword_retrieve(db_path, query, source_type="product", limit=limit)


def search_sales_playbook(db_path, query: str, *, limit: int = 5) -> list[dict]:
    return keyword_retrieve(db_path, query, source_type="playbook", limit=limit)


def _seed_chunks(db_path, chunks: list[dict]) -> int:
    existing = storage.list_knowledge_chunks(db_path)
    existing_keys = {
        (row["source_type"], row["source_name"], row["chunk_text"])
        for row in existing
    }
    inserted = 0
    for chunk in chunks:
        key = (chunk["source_type"], chunk["source_name"], chunk["chunk_text"])
        if key in existing_keys:
            continue
        storage.save_knowledge_chunk(
            db_path,
            {
                "source_type": chunk["source_type"],
                "source_name": chunk["source_name"],
                "chunk_text": chunk["chunk_text"],
                "tags_json": json.dumps(_dedupe_preserve_order(chunk["tags"]), ensure_ascii=False),
                "retrieval_metadata_json": json.dumps(chunk["retrieval_metadata"], ensure_ascii=False),
            },
        )
        inserted += 1
    return inserted


def sample_product_chunks() -> list[dict]:
    return _load_seed_chunks("seed_product_knowledge.json")


def sample_playbook_chunks() -> list[dict]:
    return _load_seed_chunks("seed_sales_playbook.json")


def seed_knowledge_chunks(db_path) -> dict:
    product_inserted = _seed_chunks(db_path, sample_product_chunks())
    playbook_inserted = _seed_chunks(db_path, sample_playbook_chunks())
    return {"product": product_inserted, "playbook": playbook_inserted}
