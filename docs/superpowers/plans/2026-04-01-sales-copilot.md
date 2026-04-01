# Sales Copilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local enterprise-style sales workbench that uploads customer profile and meeting note files, runs a LangGraph workflow with DeepSeek-powered reasoning, uses RAG and long-term account memory, and simulates CRM updates plus follow-up tasks.

**Architecture:** Keep the existing `job agent` feature intact and build the new enterprise feature in a separate `sales_copilot/` package. Use deterministic storage and tool layers for all reads and writes, a provider-based `llm/` layer for DeepSeek API integration, and a Streamlit workbench UI that surfaces workflow state, retrieval context, CRM write-back previews, and task outputs.

**Tech Stack:** Python, LangGraph, Streamlit, SQLite, requests, DeepSeek API, pytest

---

## File Structure

**Modify**
- `D:\minimind\requirements.txt`
- `D:\minimind\README.md`

**Create**
- `D:\minimind\sales_copilot\__init__.py`
- `D:\minimind\sales_copilot\schemas.py`
- `D:\minimind\sales_copilot\state.py`
- `D:\minimind\sales_copilot\storage.py`
- `D:\minimind\sales_copilot\tools.py`
- `D:\minimind\sales_copilot\prompts.py`
- `D:\minimind\sales_copilot\graph.py`
- `D:\minimind\sales_copilot\runner.py`
- `D:\minimind\llm\__init__.py`
- `D:\minimind\llm\base.py`
- `D:\minimind\llm\deepseek_client.py`
- `D:\minimind\scripts\sales_copilot_web_demo.py`
- `D:\minimind\scripts\sales_copilot_web_utils.py`
- `D:\minimind\data\sales_copilot\seed_accounts.json`
- `D:\minimind\data\sales_copilot\seed_product_knowledge.json`
- `D:\minimind\data\sales_copilot\seed_sales_playbook.json`
- `D:\minimind\data\sales_copilot\sample_customer_profile.md`
- `D:\minimind\data\sales_copilot\sample_meeting_note.md`
- `D:\minimind\tests\llm\test_deepseek_client.py`
- `D:\minimind\tests\sales_copilot\test_schemas.py`
- `D:\minimind\tests\sales_copilot\test_storage.py`
- `D:\minimind\tests\sales_copilot\test_tools.py`
- `D:\minimind\tests\sales_copilot\test_prompts.py`
- `D:\minimind\tests\sales_copilot\test_graph.py`
- `D:\minimind\tests\sales_copilot\test_runner.py`
- `D:\minimind\tests\scripts\test_sales_copilot_web_utils.py`

**Responsibilities**
- `sales_copilot/schemas.py`: typed payloads for accounts, meetings, tasks, CRM updates, and dashboard outputs
- `sales_copilot/state.py`: LangGraph state definition
- `sales_copilot/storage.py`: SQLite schema and persistence helpers
- `sales_copilot/tools.py`: deterministic file ingestion, retrieval, memory, and CRM simulation helpers
- `sales_copilot/prompts.py`: all prompt builders for DeepSeek-powered nodes
- `sales_copilot/graph.py`: node wiring and conditional routing
- `sales_copilot/runner.py`: top-level orchestration entrypoint
- `llm/base.py`: provider interface
- `llm/deepseek_client.py`: DeepSeek transport and response normalization
- `scripts/sales_copilot_web_demo.py`: workbench UI
- `scripts/sales_copilot_web_utils.py`: UI-side helpers and formatting

## Task 1: Scaffold The Sales Copilot Package

**Files:**
- Modify: `D:\minimind\requirements.txt`
- Create: `D:\minimind\sales_copilot\__init__.py`
- Create: `D:\minimind\sales_copilot\schemas.py`
- Create: `D:\minimind\tests\sales_copilot\test_schemas.py`

- [ ] **Step 1: Write the failing schema test**

```python
from sales_copilot.schemas import AccountRecord, MeetingSummary, TaskRecord


def test_sales_copilot_schema_objects_dump_expected_keys():
    account = AccountRecord(
        name="Acme Robotics",
        industry="Manufacturing",
        size_segment="Mid-Market",
        status="active",
        opportunity_stage="discovery",
    )
    meeting = MeetingSummary(
        account_name="Acme Robotics",
        customer_roles=["CTO"],
        confirmed_needs=["Private deployment"],
        objections=["Budget uncertainty"],
        next_steps=["Send deployment proposal"],
    )
    task = TaskRecord(
        account_name="Acme Robotics",
        title="Send deployment proposal",
        description="Send a tailored proposal before Friday",
        priority="high",
        status="open",
    )

    assert account.model_dump()["name"] == "Acme Robotics"
    assert meeting.model_dump()["customer_roles"] == ["CTO"]
    assert task.model_dump()["priority"] == "high"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest D:\minimind\tests\sales_copilot\test_schemas.py -q`

Expected: FAIL with `ModuleNotFoundError` or missing schema classes.

- [ ] **Step 3: Write minimal package and schema implementation**

```python
# D:\minimind\sales_copilot\__init__.py
"""Sales Copilot package."""
```

```python
# D:\minimind\sales_copilot\schemas.py
from pydantic import BaseModel, Field


class AccountRecord(BaseModel):
    name: str
    industry: str = ""
    size_segment: str = ""
    status: str
    opportunity_stage: str


class MeetingSummary(BaseModel):
    account_name: str
    customer_roles: list[str] = Field(default_factory=list)
    confirmed_needs: list[str] = Field(default_factory=list)
    objections: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class TaskRecord(BaseModel):
    account_name: str
    title: str
    description: str
    priority: str
    status: str
```

- [ ] **Step 4: Add dependency line if missing**

```text
# D:\minimind\requirements.txt
requests
langgraph
streamlit
pytest
```

- [ ] **Step 5: Run test to verify it passes**

Run: `& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest D:\minimind\tests\sales_copilot\test_schemas.py -q`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add D:\minimind\requirements.txt D:\minimind\sales_copilot\__init__.py D:\minimind\sales_copilot\schemas.py D:\minimind\tests\sales_copilot\test_schemas.py
git commit -m "feat: scaffold sales copilot package"
```

## Task 2: Add SQLite Storage For Accounts, Meetings, Tasks, Memory, CRM Updates, And Knowledge

**Files:**
- Create: `D:\minimind\sales_copilot\storage.py`
- Create: `D:\minimind\tests\sales_copilot\test_storage.py`

- [ ] **Step 1: Write the failing storage test**

```python
from pathlib import Path

from sales_copilot.storage import init_storage, list_accounts, save_account


def test_storage_creates_tables_and_persists_accounts(tmp_path: Path):
    db_path = tmp_path / "sales_copilot.db"
    init_storage(db_path)
    save_account(
        db_path,
        {
            "name": "Acme Robotics",
            "industry": "Manufacturing",
            "size_segment": "Mid-Market",
            "status": "active",
            "opportunity_stage": "discovery",
        },
    )

    rows = list_accounts(db_path)

    assert len(rows) == 1
    assert rows[0]["name"] == "Acme Robotics"
    assert rows[0]["opportunity_stage"] == "discovery"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest D:\minimind\tests\sales_copilot\test_storage.py::test_storage_creates_tables_and_persists_accounts -q`

Expected: FAIL because `sales_copilot.storage` does not exist.

- [ ] **Step 3: Implement storage initialization and account persistence**

```python
import sqlite3
from pathlib import Path


def init_storage(db_path) -> None:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                industry TEXT NOT NULL,
                size_segment TEXT NOT NULL,
                status TEXT NOT NULL,
                opportunity_stage TEXT NOT NULL,
                last_contact_at TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS meeting_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                meeting_title TEXT NOT NULL,
                meeting_note_raw TEXT NOT NULL,
                meeting_summary_json TEXT NOT NULL,
                lead_score INTEGER NOT NULL,
                priority TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                meeting_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                priority TEXT NOT NULL,
                due_at TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS account_memory (
                account_id INTEGER PRIMARY KEY,
                confirmed_needs_json TEXT NOT NULL,
                budget_signals_json TEXT NOT NULL,
                timeline_signals_json TEXT NOT NULL,
                decision_makers_json TEXT NOT NULL,
                risk_flags_json TEXT NOT NULL,
                recommended_next_step TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS crm_updates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                meeting_id INTEGER NOT NULL,
                update_type TEXT NOT NULL,
                before_json TEXT NOT NULL,
                after_json TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS knowledge_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT NOT NULL,
                source_name TEXT NOT NULL,
                chunk_text TEXT NOT NULL,
                tags_json TEXT NOT NULL,
                retrieval_metadata_json TEXT NOT NULL
            );
            """
        )


def save_account(db_path, record: dict) -> int:
    init_storage(db_path)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO accounts (name, industry, size_segment, status, opportunity_stage)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                record["name"],
                record["industry"],
                record["size_segment"],
                record["status"],
                record["opportunity_stage"],
            ),
        )
        conn.commit()
        return cursor.lastrowid


def list_accounts(db_path) -> list[dict]:
    init_storage(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM accounts ORDER BY id ASC").fetchall()
    return [dict(row) for row in rows]


def save_meeting_record(db_path, record: dict) -> int:
    init_storage(db_path)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO meeting_records (account_id, meeting_title, meeting_note_raw, meeting_summary_json, lead_score, priority)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                record["account_id"],
                record["meeting_title"],
                record["meeting_note_raw"],
                record["meeting_summary_json"],
                record["lead_score"],
                record["priority"],
            ),
        )
        conn.commit()
        return cursor.lastrowid


def list_meeting_records(db_path) -> list[dict]:
    init_storage(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM meeting_records ORDER BY id ASC").fetchall()
    return [dict(row) for row in rows]


def save_task_record(db_path, record: dict) -> int:
    init_storage(db_path)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO tasks (account_id, meeting_id, title, description, priority, due_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["account_id"],
                record["meeting_id"],
                record["title"],
                record["description"],
                record["priority"],
                record["due_at"],
                record["status"],
            ),
        )
        conn.commit()
        return cursor.lastrowid


def list_tasks(db_path) -> list[dict]:
    init_storage(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM tasks ORDER BY id ASC").fetchall()
    return [dict(row) for row in rows]


def upsert_account_memory(db_path, account_id: int, payload: dict) -> None:
    init_storage(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO account_memory (
                account_id, confirmed_needs_json, budget_signals_json, timeline_signals_json,
                decision_makers_json, risk_flags_json, recommended_next_step, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(account_id) DO UPDATE SET
                confirmed_needs_json=excluded.confirmed_needs_json,
                budget_signals_json=excluded.budget_signals_json,
                timeline_signals_json=excluded.timeline_signals_json,
                decision_makers_json=excluded.decision_makers_json,
                risk_flags_json=excluded.risk_flags_json,
                recommended_next_step=excluded.recommended_next_step,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                account_id,
                payload["confirmed_needs_json"],
                payload["budget_signals_json"],
                payload["timeline_signals_json"],
                payload["decision_makers_json"],
                payload["risk_flags_json"],
                payload["recommended_next_step"],
            ),
        )
        conn.commit()


def get_account_memory(db_path, account_id: int) -> dict | None:
    init_storage(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM account_memory WHERE account_id = ?", (account_id,)).fetchone()
    return dict(row) if row else None


def save_crm_update(db_path, payload: dict) -> int:
    init_storage(db_path)
    with sqlite3.connect(db_path) as conn:
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
        conn.commit()
        return cursor.lastrowid


def list_crm_updates(db_path) -> list[dict]:
    init_storage(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM crm_updates ORDER BY id ASC").fetchall()
    return [dict(row) for row in rows]


def save_knowledge_chunk(db_path, payload: dict) -> int:
    init_storage(db_path)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO knowledge_chunks (source_type, source_name, chunk_text, tags_json, retrieval_metadata_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                payload["source_type"],
                payload["source_name"],
                payload["chunk_text"],
                payload["tags_json"],
                payload["retrieval_metadata_json"],
            ),
        )
        conn.commit()
        return cursor.lastrowid


def list_knowledge_chunks(db_path, source_type: str | None = None) -> list[dict]:
    init_storage(db_path)
    query = "SELECT * FROM knowledge_chunks"
    params: tuple = ()
    if source_type is not None:
        query += " WHERE source_type = ?"
        params = (source_type,)
    query += " ORDER BY id ASC"
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_account_by_id(db_path, account_id: int) -> dict:
    init_storage(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
    return dict(row)


def update_account_stage_and_status(db_path, *, account_id: int, status: str, opportunity_stage: str, last_contact_at: str) -> None:
    init_storage(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE accounts
            SET status = ?, opportunity_stage = ?, last_contact_at = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, opportunity_stage, last_contact_at, account_id),
        )
        conn.commit()
```

- [ ] **Step 4: Run focused test to verify it passes**

Run: `& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest D:\minimind\tests\sales_copilot\test_storage.py::test_storage_creates_tables_and_persists_accounts -q`

Expected: PASS

- [ ] **Step 5: Expand tests for meetings, tasks, memory, CRM updates, and knowledge rows**

```python
def test_storage_supports_meetings_tasks_memory_and_crm_updates(tmp_path: Path):
    db_path = tmp_path / "sales_copilot.db"
    init_storage(db_path)
    account_id = save_account(
        db_path,
        {
            "name": "Acme Robotics",
            "industry": "Manufacturing",
            "size_segment": "Mid-Market",
            "status": "active",
            "opportunity_stage": "discovery",
        },
    )
    meeting_id = save_meeting_record(
        db_path,
        {
            "account_id": account_id,
            "meeting_title": "Discovery Call",
            "meeting_note_raw": "CTO asked for deployment options.",
            "meeting_summary_json": "{\"confirmed_needs\": [\"private deployment\"]}",
            "lead_score": 88,
            "priority": "high",
        },
    )
    save_task_record(
        db_path,
        {
            "account_id": account_id,
            "meeting_id": meeting_id,
            "title": "Send proposal",
            "description": "Send tailored proposal before Friday",
            "priority": "high",
            "due_at": "2026-04-03",
            "status": "open",
        },
    )
    upsert_account_memory(
        db_path,
        account_id,
        {
            "confirmed_needs_json": "[\"private deployment\"]",
            "budget_signals_json": "[\"budget approved\"]",
            "timeline_signals_json": "[\"this quarter\"]",
            "decision_makers_json": "[\"CTO\"]",
            "risk_flags_json": "[\"security_review\"]",
            "recommended_next_step": "Book technical demo",
        },
    )
    save_crm_update(
        db_path,
        {
            "account_id": account_id,
            "meeting_id": meeting_id,
            "update_type": "account_stage",
            "before_json": "{\"opportunity_stage\": \"discovery\"}",
            "after_json": "{\"opportunity_stage\": \"proposal\"}",
        },
    )

    meeting_rows = list_meeting_records(db_path)
    task_rows = list_tasks(db_path)
    memory_row = get_account_memory(db_path, account_id)
    crm_rows = list_crm_updates(db_path)

    assert meeting_rows[0]["priority"] == "high"
    assert task_rows[0]["status"] == "open"
    assert memory_row["recommended_next_step"] == "Book technical demo"
    assert crm_rows[0]["update_type"] == "account_stage"
```

- [ ] **Step 6: Commit**

```bash
git add D:\minimind\sales_copilot\storage.py D:\minimind\tests\sales_copilot\test_storage.py
git commit -m "feat: add sales copilot sqlite storage"
```

## Task 3: Implement Deterministic Ingestion, Retrieval, Memory, And CRM Tools

**Files:**
- Create: `D:\minimind\sales_copilot\tools.py`
- Create: `D:\minimind\data\sales_copilot\seed_accounts.json`
- Create: `D:\minimind\data\sales_copilot\seed_product_knowledge.json`
- Create: `D:\minimind\data\sales_copilot\seed_sales_playbook.json`
- Create: `D:\minimind\data\sales_copilot\sample_customer_profile.md`
- Create: `D:\minimind\data\sales_copilot\sample_meeting_note.md`
- Create: `D:\minimind\tests\sales_copilot\test_tools.py`

- [ ] **Step 1: Write failing tool tests for ingestion and retrieval**

```python
from pathlib import Path

from sales_copilot.tools import ingest_text_file, keyword_retrieve


def test_ingest_text_file_reads_markdown_content(tmp_path: Path):
    file_path = tmp_path / "profile.md"
    file_path.write_text("# Acme Robotics\nNeed private deployment", encoding="utf-8")

    payload = ingest_text_file(file_path)

    assert payload["filename"] == "profile.md"
    assert "private deployment" in payload["text"]


def test_keyword_retrieve_returns_top_ranked_chunk():
    rows = [
        {"chunk_text": "private deployment and compliance", "source_name": "product"},
        {"chunk_text": "retail use case and coupons", "source_name": "playbook"},
    ]

    result = keyword_retrieve("compliance deployment", rows, top_k=1)

    assert result[0]["source_name"] == "product"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest D:\minimind\tests\sales_copilot\test_tools.py -q`

Expected: FAIL because `sales_copilot.tools` does not exist.

- [ ] **Step 3: Implement file ingestion and lexical retrieval helpers**

```python
from pathlib import Path
import re


def ingest_text_file(path) -> dict:
    path = Path(path)
    return {
        "filename": path.name,
        "text": path.read_text(encoding="utf-8"),
        "source_path": str(path),
    }


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9_]+", text.lower())


def keyword_retrieve(query: str, rows: list[dict], top_k: int = 3) -> list[dict]:
    query_tokens = set(tokenize(query))
    scored = []
    for row in rows:
        row_tokens = set(tokenize(row["chunk_text"]))
        score = len(query_tokens & row_tokens)
        scored.append((score, row))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [row for score, row in scored if score > 0][:top_k]
```

- [ ] **Step 4: Add deterministic account-history, open-task, CRM, and memory tools**

```python
def search_account_history(db_path, account_id: int) -> list[dict]:
    return [row for row in list_meeting_records(db_path) if row["account_id"] == account_id]


def get_open_tasks(db_path, account_id: int) -> list[dict]:
    return [row for row in list_tasks(db_path) if row["account_id"] == account_id and row["status"] == "open"]


def update_crm_account(db_path, account_id: int, after: dict) -> int:
    before = get_account_by_id(db_path, account_id)
    update_account_stage_and_status(
        db_path,
        account_id=account_id,
        status=after["status"],
        opportunity_stage=after["opportunity_stage"],
        last_contact_at=after["last_contact_at"],
    )
    return save_crm_update(
        db_path,
        {
            "account_id": account_id,
            "meeting_id": after["meeting_id"],
            "update_type": "account_state",
            "before_json": json.dumps(before, ensure_ascii=False),
            "after_json": json.dumps(after, ensure_ascii=False),
        },
    )


def append_account_memory(db_path, account_id: int, memory_payload: dict) -> None:
    existing = get_account_memory(db_path, account_id) or {
        "confirmed_needs_json": "[]",
        "budget_signals_json": "[]",
        "timeline_signals_json": "[]",
        "decision_makers_json": "[]",
        "risk_flags_json": "[]",
        "recommended_next_step": "",
    }
    merged = merge_account_memory(existing, memory_payload)
    upsert_account_memory(db_path, account_id, merged)


def search_product_knowledge(db_path, query: str, top_k: int = 3) -> list[dict]:
    rows = list_knowledge_chunks(db_path, source_type="product")
    return keyword_retrieve(query, rows, top_k=top_k)


def search_sales_playbook(db_path, query: str, top_k: int = 3) -> list[dict]:
    rows = list_knowledge_chunks(db_path, source_type="playbook")
    return keyword_retrieve(query, rows, top_k=top_k)


def seed_knowledge_chunks(db_path, rows: list[dict]) -> None:
    for row in rows:
        save_knowledge_chunk(db_path, row)


def sample_product_chunks() -> list[dict]:
    return [
        {
            "source_type": "product",
            "source_name": "deployment-options",
            "chunk_text": "Private deployment supports regulated industries with on-prem networking and audit controls.",
            "tags_json": '["deployment", "security", "compliance"]',
            "retrieval_metadata_json": '{"priority": 1}',
        }
    ]


def sample_playbook_chunks() -> list[dict]:
    return [
        {
            "source_type": "playbook",
            "source_name": "pricing-playbook",
            "chunk_text": "Budget objections should be handled with phased rollout and ROI framing.",
            "tags_json": '["budget", "objection-handling"]',
            "retrieval_metadata_json": '{"priority": 1}',
        }
    ]


def merge_account_memory(existing: dict, memory_payload: dict) -> dict:
    return {
        "confirmed_needs_json": json.dumps(
            sorted(set(json.loads(existing["confirmed_needs_json"]) + memory_payload.get("confirmed_needs", []))),
            ensure_ascii=False,
        ),
        "budget_signals_json": json.dumps(memory_payload.get("budget_signals", []), ensure_ascii=False),
        "timeline_signals_json": json.dumps(memory_payload.get("timeline_signals", []), ensure_ascii=False),
        "decision_makers_json": json.dumps(memory_payload.get("decision_makers", []), ensure_ascii=False),
        "risk_flags_json": json.dumps(
            sorted(set(json.loads(existing["risk_flags_json"]) + memory_payload.get("risk_flags", []))),
            ensure_ascii=False,
        ),
        "recommended_next_step": memory_payload.get("recommended_next_step", existing["recommended_next_step"]),
    }
```

- [ ] **Step 5: Seed sample knowledge and sample files**

```json
[
  {
    "source_type": "product",
    "source_name": "deployment-options",
    "chunk_text": "Private deployment supports regulated industries with on-prem networking and audit controls.",
    "tags_json": ["deployment", "security", "compliance"],
    "retrieval_metadata_json": {"priority": 1}
  }
]
```

- [ ] **Step 6: Run full tools test suite**

Run: `& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest D:\minimind\tests\sales_copilot\test_tools.py -q`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add D:\minimind\sales_copilot\tools.py D:\minimind\data\sales_copilot D:\minimind\tests\sales_copilot\test_tools.py
git commit -m "feat: add sales copilot ingestion and retrieval tools"
```

## Task 4: Add DeepSeek Provider And Prompt Builders

**Files:**
- Create: `D:\minimind\llm\__init__.py`
- Create: `D:\minimind\llm\base.py`
- Create: `D:\minimind\llm\deepseek_client.py`
- Create: `D:\minimind\sales_copilot\prompts.py`
- Create: `D:\minimind\tests\llm\test_deepseek_client.py`
- Create: `D:\minimind\tests\sales_copilot\test_prompts.py`

- [ ] **Step 1: Write failing prompt and client tests**

```python
from sales_copilot.prompts import build_meeting_parse_messages


def test_build_meeting_parse_messages_includes_profile_and_note():
    messages = build_meeting_parse_messages(
        customer_profile_text="Acme Robotics needs compliance support",
        meeting_note_text="CTO asked for private deployment pricing",
    )

    assert messages[0]["role"] == "system"
    assert "private deployment pricing" in messages[1]["content"]
```

```python
from llm.deepseek_client import DeepSeekClient


def test_deepseek_client_builds_expected_request_payload(monkeypatch):
    captured = {}

    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "{\"score\": 85}"}}]}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return DummyResponse()

    monkeypatch.setattr("requests.post", fake_post)
    client = DeepSeekClient(api_key="demo", base_url="https://api.deepseek.com", model="deepseek-chat")

    text = client.complete([{"role": "user", "content": "hello"}])

    assert captured["url"].endswith("/chat/completions")
    assert captured["json"]["model"] == "deepseek-chat"
    assert text == "{\"score\": 85}"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest D:\minimind\tests\llm\test_deepseek_client.py D:\minimind\tests\sales_copilot\test_prompts.py -q`

Expected: FAIL because the client and prompt module do not exist.

- [ ] **Step 3: Implement provider interface and DeepSeek client**

```python
# D:\minimind\llm\base.py
from abc import ABC, abstractmethod


class BaseLLMClient(ABC):
    @abstractmethod
    def complete(self, messages: list[dict], response_format: dict | None = None) -> str:
        raise NotImplementedError
```

```python
# D:\minimind\llm\deepseek_client.py
import requests

from llm.base import BaseLLMClient


class DeepSeekClient(BaseLLMClient):
    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com", model: str = "deepseek-chat"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def complete(self, messages: list[dict], response_format: dict | None = None) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "stream": False,
        }
        if response_format is not None:
            payload["response_format"] = response_format
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
```

- [ ] **Step 4: Implement prompt builders**

```python
def build_meeting_parse_messages(*, customer_profile_text: str, meeting_note_text: str) -> list[dict]:
    return [
        {
            "role": "system",
            "content": "Extract structured sales meeting facts as JSON. Do not invent missing facts.",
        },
        {
            "role": "user",
            "content": (
                f"Customer profile:\n{customer_profile_text}\n\n"
                f"Meeting note:\n{meeting_note_text}\n\n"
                "Return JSON with customer_roles, confirmed_needs, objections, budget_signals, timeline_signals, competitors, next_steps."
            ),
        },
    ]


def build_lead_scoring_messages(*, customer_profile_text: str, meeting_summary: dict, retrieved_docs: list[dict], account_memory: dict) -> list[dict]:
    return [
        {
            "role": "system",
            "content": "Score the sales lead as JSON. Use retrieved context and account memory. Do not invent facts.",
        },
        {
            "role": "user",
            "content": (
                f"Customer profile:\n{customer_profile_text}\n\n"
                f"Meeting summary:\n{meeting_summary}\n\n"
                f"Retrieved context:\n{retrieved_docs}\n\n"
                f"Account memory:\n{account_memory}\n\n"
                "Return JSON with lead_score, lead_priority, opportunity_stage, risk_flags."
            ),
        },
    ]


def build_followup_plan_messages(*, meeting_summary: dict, opportunity_stage: str, risk_flags: list[str]) -> list[dict]:
    return [
        {
            "role": "system",
            "content": "Generate a concise follow-up plan as JSON with next action summary and task list.",
        },
        {
            "role": "user",
            "content": (
                f"Meeting summary:\n{meeting_summary}\n\n"
                f"Opportunity stage: {opportunity_stage}\n"
                f"Risk flags: {risk_flags}\n\n"
                "Return JSON with summary, recommended_materials, and tasks."
            ),
        },
    ]
```

- [ ] **Step 5: Add prompt tests for scoring, follow-up, CRM update, and dashboard summary builders**

```python
def test_build_lead_scoring_messages_mentions_retrieved_context():
    messages = build_lead_scoring_messages(
        customer_profile_text="Acme Robotics is evaluating private deployment.",
        meeting_summary={"confirmed_needs": ["private deployment"], "objections": ["budget"]},
        retrieved_docs=[
            {"source_name": "deployment-options", "chunk_text": "Private deployment is supported."},
            {"source_name": "pricing-playbook", "chunk_text": "Budget objections should be handled with phased rollout."},
        ],
        account_memory={"recommended_next_step": "Schedule technical validation"},
    )
    assert "retrieved context" in messages[1]["content"].lower()
```

- [ ] **Step 6: Run test suite**

Run: `& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest D:\minimind\tests\llm\test_deepseek_client.py D:\minimind\tests\sales_copilot\test_prompts.py -q`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add D:\minimind\llm D:\minimind\sales_copilot\prompts.py D:\minimind\tests\llm\test_deepseek_client.py D:\minimind\tests\sales_copilot\test_prompts.py
git commit -m "feat: add deepseek provider and sales prompts"
```

## Task 5: Define Workflow State And Routing Rules

**Files:**
- Create: `D:\minimind\sales_copilot\state.py`
- Create: `D:\minimind\sales_copilot\graph.py`
- Create: `D:\minimind\tests\sales_copilot\test_graph.py`

- [ ] **Step 1: Write the failing graph routing test**

```python
from sales_copilot.graph import route_after_lead_evaluation


def test_route_after_lead_evaluation_returns_need_more_info():
    state = {"meeting_summary": {}, "lead_score": 0, "lead_priority": "unknown", "risk_flags": ["missing_budget"]}

    route = route_after_lead_evaluation(state)

    assert route == "need_more_info"


def test_route_after_lead_evaluation_returns_high_priority_follow_up():
    state = {"meeting_summary": {"confirmed_needs": ["private deployment"]}, "lead_score": 90, "lead_priority": "high", "risk_flags": []}

    route = route_after_lead_evaluation(state)

    assert route == "high_priority_follow_up"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest D:\minimind\tests\sales_copilot\test_graph.py -q`

Expected: FAIL because graph module does not exist.

- [ ] **Step 3: Define workflow state**

```python
from typing import TypedDict


class SalesCopilotState(TypedDict, total=False):
    account_id: int
    meeting_id: int
    customer_profile_raw: str
    meeting_note_raw: str
    customer_profile_structured: dict
    meeting_summary: dict
    retrieved_docs: list[dict]
    account_memory: dict
    open_tasks: list[dict]
    lead_score: int
    lead_priority: str
    opportunity_stage: str
    risk_flags: list[str]
    follow_up_plan: dict
    crm_update_payload: dict
    crm_update_ids: list[int]
    task_payload: list[dict]
    dashboard_output: dict
    workflow_log: list[str]
```

- [ ] **Step 4: Implement routing helpers and graph skeleton**

```python
from langgraph.graph import END, StateGraph

from sales_copilot.state import SalesCopilotState


def route_after_lead_evaluation(state: SalesCopilotState) -> str:
    if not state.get("meeting_summary") or state.get("risk_flags") == ["missing_required_facts"]:
        return "need_more_info"
    score = state["lead_score"]
    if score < 50:
        return "low_priority_nurture"
    if score < 80:
        return "standard_follow_up"
    return "high_priority_follow_up"


def build_sales_copilot_graph(*, llm_client, database_path):
    builder = StateGraph(SalesCopilotState)
    builder.add_node("ingest_files", ingest_files_node)
    builder.add_node("parse_meeting_note", lambda state: parse_meeting_note_node(state, llm_client))
    builder.add_node("retrieve_context", lambda state: retrieve_context_node(state, database_path))
    builder.add_node("load_account_memory", lambda state: load_account_memory_node(state, database_path))
    builder.add_node("evaluate_lead", lambda state: evaluate_lead_node(state, llm_client))
    builder.add_node("need_more_info", need_more_info_node)
    builder.add_node("low_priority_nurture", low_priority_nurture_node)
    builder.add_node("standard_follow_up", lambda state: standard_follow_up_node(state, llm_client))
    builder.add_node("high_priority_follow_up", lambda state: high_priority_follow_up_node(state, llm_client))
    builder.add_node("write_back_crm", lambda state: write_back_crm_node(state, database_path))
    builder.add_node("generate_dashboard_output", generate_dashboard_output_node)
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
    builder.add_edge("need_more_info", "generate_dashboard_output")
    builder.add_edge("low_priority_nurture", "write_back_crm")
    builder.add_edge("standard_follow_up", "write_back_crm")
    builder.add_edge("high_priority_follow_up", "write_back_crm")
    builder.add_edge("write_back_crm", "generate_dashboard_output")
    builder.add_edge("generate_dashboard_output", END)
    return builder.compile()
```

- [ ] **Step 5: Add graph tests for all three scoring branches**

```python
def test_route_after_lead_evaluation_returns_low_priority_nurture():
    state = {"meeting_summary": {"confirmed_needs": ["pricing"]}, "lead_score": 35, "lead_priority": "low", "risk_flags": []}
    assert route_after_lead_evaluation(state) == "low_priority_nurture"


def test_route_after_lead_evaluation_returns_standard_follow_up():
    state = {"meeting_summary": {"confirmed_needs": ["demo"]}, "lead_score": 70, "lead_priority": "medium", "risk_flags": []}
    assert route_after_lead_evaluation(state) == "standard_follow_up"
```

- [ ] **Step 6: Run graph tests**

Run: `& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest D:\minimind\tests\sales_copilot\test_graph.py -q`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add D:\minimind\sales_copilot\state.py D:\minimind\sales_copilot\graph.py D:\minimind\tests\sales_copilot\test_graph.py
git commit -m "feat: add sales copilot workflow state and routing"
```

## Task 6: Implement Workflow Nodes And Runner

**Files:**
- Create: `D:\minimind\sales_copilot\runner.py`
- Modify: `D:\minimind\sales_copilot\graph.py`
- Create: `D:\minimind\tests\sales_copilot\test_runner.py`

- [ ] **Step 1: Write the failing runner test**

```python
from sales_copilot.runner import run_sales_copilot


class FakeLLM:
    def __init__(self):
        self.calls = []

    def complete(self, messages, response_format=None):
        self.calls.append(messages)
        return '{"lead_score": 88, "lead_priority": "high", "opportunity_stage": "proposal", "risk_flags": [], "follow_up_plan": {"summary": "Send proposal"}, "task_payload": [{"title": "Send proposal", "priority": "high"}]}'


def test_run_sales_copilot_returns_dashboard_and_crm_ids(tmp_path):
    result = run_sales_copilot(
        customer_profile_text="Acme Robotics is a manufacturing company.",
        meeting_note_text="CTO requested a proposal for private deployment.",
        database_path=tmp_path / "sales.db",
        llm_client=FakeLLM(),
    )

    assert result["lead_score"] == 88
    assert result["dashboard_output"]["account_name"] == "Acme Robotics"
    assert result["crm_update_ids"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest D:\minimind\tests\sales_copilot\test_runner.py -q`

Expected: FAIL because the runner and graph nodes are incomplete.

- [ ] **Step 3: Implement node functions with injected tools and llm client**

```python
def parse_meeting_note_node(state, llm_client):
    messages = build_meeting_parse_messages(
        customer_profile_text=state["customer_profile_raw"],
        meeting_note_text=state["meeting_note_raw"],
    )
    content = llm_client.complete(messages, response_format={"type": "json_object"})
    payload = json.loads(content)
    return {"meeting_summary": payload, "workflow_log": state.get("workflow_log", []) + ["parse_meeting_note"]}
```

```python
def ingest_files_node(state):
    return {
        "customer_profile_structured": {"account_name": state["customer_profile_raw"].splitlines()[0].replace("# ", "")},
        "workflow_log": state.get("workflow_log", []) + ["ingest_files"],
    }


def retrieve_context_node(state, database_path):
    query = " ".join(state["meeting_summary"].get("confirmed_needs", [])) or state["meeting_note_raw"]
    docs = search_product_knowledge(database_path, query, top_k=2) + search_sales_playbook(database_path, query, top_k=2)
    if state.get("account_id"):
        docs += search_account_history(database_path, state["account_id"])[:2]
    return {"retrieved_docs": docs, "workflow_log": state["workflow_log"] + ["retrieve_context"]}


def load_account_memory_node(state, database_path):
    memory = get_account_memory(database_path, state["account_id"]) if state.get("account_id") else None
    tasks = get_open_tasks(database_path, state["account_id"]) if state.get("account_id") else []
    return {"account_memory": memory or {}, "open_tasks": tasks, "workflow_log": state["workflow_log"] + ["load_account_memory"]}


def evaluate_lead_node(state, llm_client):
    messages = build_lead_scoring_messages(
        customer_profile_text=state["customer_profile_raw"],
        meeting_summary=state["meeting_summary"],
        retrieved_docs=state["retrieved_docs"],
        account_memory=state["account_memory"],
    )
    payload = json.loads(llm_client.complete(messages, response_format={"type": "json_object"}))
    return {
        "lead_score": payload["lead_score"],
        "lead_priority": payload["lead_priority"],
        "opportunity_stage": payload["opportunity_stage"],
        "risk_flags": payload["risk_flags"],
        "workflow_log": state["workflow_log"] + ["evaluate_lead"],
    }


def need_more_info_node(state):
    return {"follow_up_plan": {"summary": "Collect missing budget, timeline, and buyer-role details."}, "workflow_log": state["workflow_log"] + ["need_more_info"]}


def low_priority_nurture_node(state):
    return {"follow_up_plan": {"summary": "Place account into nurture flow with lightweight educational content."}, "workflow_log": state["workflow_log"] + ["low_priority_nurture"]}


def standard_follow_up_node(state, llm_client):
    payload = json.loads(
        llm_client.complete(
            build_followup_plan_messages(
                meeting_summary=state["meeting_summary"],
                opportunity_stage=state["opportunity_stage"],
                risk_flags=state["risk_flags"],
            ),
            response_format={"type": "json_object"},
        )
    )
    return {"follow_up_plan": payload, "task_payload": payload["tasks"], "workflow_log": state["workflow_log"] + ["standard_follow_up"]}


def high_priority_follow_up_node(state, llm_client):
    payload = json.loads(
        llm_client.complete(
            build_followup_plan_messages(
                meeting_summary=state["meeting_summary"],
                opportunity_stage=state["opportunity_stage"],
                risk_flags=state["risk_flags"],
            ),
            response_format={"type": "json_object"},
        )
    )
    return {"follow_up_plan": payload, "task_payload": payload["tasks"], "workflow_log": state["workflow_log"] + ["high_priority_follow_up"]}


def write_back_crm_node(state, database_path):
    crm_update_id = update_crm_account(
        database_path,
        state["account_id"],
        {
            "meeting_id": state.get("meeting_id", 0),
            "status": "active",
            "opportunity_stage": state["opportunity_stage"],
            "last_contact_at": "2026-04-01",
        },
    )
    return {"crm_update_ids": [crm_update_id], "workflow_log": state["workflow_log"] + ["write_back_crm"]}


def generate_dashboard_output_node(state):
    return {
        "dashboard_output": {
            "account_name": state["customer_profile_structured"]["account_name"],
            "lead_score": state.get("lead_score", 0),
            "priority": state.get("lead_priority", "unknown"),
            "stage": state.get("opportunity_stage", ""),
            "summary": state["follow_up_plan"]["summary"],
        },
        "workflow_log": state["workflow_log"] + ["generate_dashboard_output"],
    }
```

- [ ] **Step 4: Implement runner entrypoint**

```python
def run_sales_copilot(
    *,
    customer_profile_text: str,
    meeting_note_text: str,
    database_path,
    llm_client,
    account_id: int | None = None,
) -> dict:
    graph = build_sales_copilot_graph(llm_client=llm_client, database_path=database_path)
    return graph.invoke(
        {
            "account_id": account_id or 0,
            "customer_profile_raw": customer_profile_text,
            "meeting_note_raw": meeting_note_text,
            "workflow_log": [],
        }
    )
```

- [ ] **Step 5: Run runner tests**

Run: `& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest D:\minimind\tests\sales_copilot\test_runner.py -q`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add D:\minimind\sales_copilot\graph.py D:\minimind\sales_copilot\runner.py D:\minimind\tests\sales_copilot\test_runner.py
git commit -m "feat: add sales copilot workflow execution"
```

## Task 7: Build The Streamlit Enterprise Workbench

**Files:**
- Create: `D:\minimind\scripts\sales_copilot_web_utils.py`
- Create: `D:\minimind\scripts\sales_copilot_web_demo.py`
- Create: `D:\minimind\tests\scripts\test_sales_copilot_web_utils.py`

- [ ] **Step 1: Write the failing UI utility test**

```python
from scripts.sales_copilot_web_utils import build_dashboard_cards


def test_build_dashboard_cards_formats_lead_summary():
    payload = build_dashboard_cards(
        {
            "lead_score": 88,
            "lead_priority": "high",
            "opportunity_stage": "proposal",
            "risk_flags": ["budget_risk"],
        }
    )

    assert payload["Lead Score"] == "88"
    assert payload["Priority"] == "high"
    assert payload["Stage"] == "proposal"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest D:\minimind\tests\scripts\test_sales_copilot_web_utils.py -q`

Expected: FAIL because the UI utility module does not exist.

- [ ] **Step 3: Implement UI helper functions**

```python
def build_dashboard_cards(result: dict) -> dict:
    return {
        "Lead Score": str(result["lead_score"]),
        "Priority": result["lead_priority"],
        "Stage": result["opportunity_stage"],
        "Risk Flags": ", ".join(result.get("risk_flags", [])) or "None",
    }
```

- [ ] **Step 4: Build the Streamlit workbench**

```python
st.set_page_config(page_title="Sales Copilot", layout="wide")
left, center, right = st.columns([1.2, 1.6, 1.2])

with left:
    customer_profile = st.text_area("Customer Profile")
    meeting_note = st.text_area("Meeting Note")
    run = st.button("Run Sales Copilot")

with center:
    st.subheader("Lead Dashboard")
    st.metric("Lead Score", result["lead_score"])
    st.metric("Priority", result["lead_priority"])
    st.metric("Stage", result["opportunity_stage"])
    st.json(result["dashboard_output"])

with right:
    st.subheader("CRM Write-Back")
    st.json(result["crm_update_payload"])
    st.subheader("Tasks")
    st.dataframe(result["task_payload"])
```

- [ ] **Step 5: Add execution log, retrieval, and memory sections to the lower half**

```python
retrieval_tab, memory_tab, workflow_tab = st.tabs(["Retrieved Context", "Account Memory", "Workflow Log"])
```

- [ ] **Step 6: Run UI helper tests and a headless Streamlit smoke run**

Run: `& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest D:\minimind\tests\scripts\test_sales_copilot_web_utils.py -q`

Run: `& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m streamlit run D:\minimind\scripts\sales_copilot_web_demo.py --server.headless true --server.port 8520`

Expected: tests PASS, Streamlit starts successfully.

- [ ] **Step 7: Commit**

```bash
git add D:\minimind\scripts\sales_copilot_web_utils.py D:\minimind\scripts\sales_copilot_web_demo.py D:\minimind\tests\scripts\test_sales_copilot_web_utils.py
git commit -m "feat: add sales copilot workbench ui"
```

## Task 8: Add End-To-End Seed Data, Retrieval Coverage, And Repeated-Account Memory Tests

**Files:**
- Modify: `D:\minimind\sales_copilot\storage.py`
- Modify: `D:\minimind\sales_copilot\tools.py`
- Modify: `D:\minimind\tests\sales_copilot\test_tools.py`
- Modify: `D:\minimind\tests\sales_copilot\test_runner.py`

- [ ] **Step 1: Write a failing repeated-account memory test**

```python
def test_repeated_account_run_reuses_prior_memory(tmp_path):
    llm = FakeLLM()
    first = run_sales_copilot(
        customer_profile_text="Acme Robotics",
        meeting_note_text="CTO requested security review.",
        database_path=tmp_path / "sales.db",
        llm_client=llm,
    )

    second = run_sales_copilot(
        customer_profile_text="Acme Robotics",
        meeting_note_text="CFO asked about deployment pricing and procurement timing.",
        database_path=tmp_path / "sales.db",
        llm_client=llm,
        account_id=first["account_id"],
    )

    assert second["account_memory"]
    assert second["open_tasks"] is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest D:\minimind\tests\sales_copilot\test_runner.py::test_repeated_account_run_reuses_prior_memory -q`

Expected: FAIL because memory reuse is not implemented yet.

- [ ] **Step 3: Implement memory merge and retrieval seeding**

```python
def merge_account_memory(existing: dict, new_summary: dict) -> dict:
    return {
        "confirmed_needs": sorted(set(existing.get("confirmed_needs", []) + new_summary.get("confirmed_needs", []))),
        "risk_flags": sorted(set(existing.get("risk_flags", []) + new_summary.get("risk_flags", []))),
        "recommended_next_step": new_summary.get("recommended_next_step", existing.get("recommended_next_step", "")),
    }
```

- [ ] **Step 4: Add retrieval tests across product and playbook corpora**

```python
def test_search_product_knowledge_uses_seed_chunks(tmp_path):
    db_path = tmp_path / "sales.db"
    init_storage(db_path)
    seed_knowledge_chunks(db_path, sample_product_chunks())
    rows = search_product_knowledge(db_path, "private deployment compliance", top_k=1)
    assert rows[0]["source_name"] == "deployment-options"


def test_search_sales_playbook_returns_relevant_objection_handling(tmp_path):
    db_path = tmp_path / "sales.db"
    init_storage(db_path)
    seed_knowledge_chunks(db_path, sample_playbook_chunks())
    rows = search_sales_playbook(db_path, "budget objection rollout", top_k=1)
    assert rows[0]["source_name"] == "pricing-playbook"
```

- [ ] **Step 5: Run storage, tools, and runner suites**

Run: `& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest D:\minimind\tests\sales_copilot\test_storage.py D:\minimind\tests\sales_copilot\test_tools.py D:\minimind\tests\sales_copilot\test_runner.py -q`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add D:\minimind\sales_copilot\storage.py D:\minimind\sales_copilot\tools.py D:\minimind\tests\sales_copilot\test_tools.py D:\minimind\tests\sales_copilot\test_runner.py
git commit -m "feat: add memory reuse and retrieval regression coverage"
```

## Task 9: Document The Feature And Run Final Verification

**Files:**
- Modify: `D:\minimind\README.md`

- [ ] **Step 1: Add a README quickstart section**

````markdown
## Sales Copilot

Run the workbench:

```powershell
& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m streamlit run D:\minimind\scripts\sales_copilot_web_demo.py
```

Required environment variables:

```powershell
$env:DEEPSEEK_API_KEY="your-key"
```
````

- [ ] **Step 2: Add architecture notes to README**

```markdown
- LangGraph orchestrates ingestion, retrieval, memory loading, lead scoring, follow-up planning, CRM simulation, and dashboard rendering.
- DeepSeek powers structured extraction and reasoning.
- All state-changing actions go through deterministic tools and SQLite persistence.
```

- [ ] **Step 3: Run the complete targeted test suite**

Run: `& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m pytest D:\minimind\tests\sales_copilot D:\minimind\tests\llm\test_deepseek_client.py D:\minimind\tests\scripts\test_sales_copilot_web_utils.py -q`

Expected: PASS

- [ ] **Step 4: Run a syntax verification pass**

Run: `& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m py_compile D:\minimind\sales_copilot\schemas.py D:\minimind\sales_copilot\state.py D:\minimind\sales_copilot\storage.py D:\minimind\sales_copilot\tools.py D:\minimind\sales_copilot\prompts.py D:\minimind\sales_copilot\graph.py D:\minimind\sales_copilot\runner.py D:\minimind\llm\base.py D:\minimind\llm\deepseek_client.py D:\minimind\scripts\sales_copilot_web_utils.py D:\minimind\scripts\sales_copilot_web_demo.py`

Expected: no output and exit code 0

- [ ] **Step 5: Run one manual demo smoke flow**

Run: `& 'D:\anaconda\envs\minimind_job_agent\python.exe' -m streamlit run D:\minimind\scripts\sales_copilot_web_demo.py`

Expected:
- UI opens
- sample profile and meeting note can be loaded
- one run produces a lead score, a task list, retrieval context, and CRM write-back preview

- [ ] **Step 6: Commit**

```bash
git add D:\minimind\README.md
git commit -m "docs: add sales copilot quickstart"
```

## Spec Coverage Check

- Goal and user journey map to Tasks 3 through 9.
- Ingestion layer maps to Task 3.
- Tool layer maps to Tasks 3, 6, and 8.
- RAG layer maps to Tasks 3 and 8.
- Memory layer maps to Tasks 2, 3, 6, and 8.
- LLM and DeepSeek provider map to Task 4.
- LangGraph workflow maps to Tasks 5 and 6.
- UI workbench maps to Task 7.
- Testing strategy maps to Tasks 1 through 9.
- Resume-facing observability maps to Tasks 6, 7, and 9 through workflow log, retrieval display, and CRM preview.

## Notes For Execution

- Keep the current `job agent` feature untouched while building `sales_copilot/`.
- Prefer deterministic local retrieval first; avoid introducing a heavy vector database in V1.
- Use injected fake LLM clients in tests instead of making real DeepSeek API calls.
- Keep all business writes inside tool or storage functions. Do not let prompt code mutate state.
