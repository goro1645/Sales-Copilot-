import sqlite3
from pathlib import Path


def _connect(db_path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_storage(db_path) -> None:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as conn:
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
                account_id INTEGER NOT NULL REFERENCES accounts(id),
                meeting_title TEXT NOT NULL,
                meeting_note_raw TEXT NOT NULL,
                meeting_summary_json TEXT NOT NULL,
                lead_score INTEGER NOT NULL,
                priority TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(account_id, id)
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL REFERENCES accounts(id),
                meeting_id INTEGER NOT NULL REFERENCES meeting_records(id),
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                priority TEXT NOT NULL,
                due_at TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id, meeting_id) REFERENCES meeting_records(account_id, id)
            );
            CREATE TABLE IF NOT EXISTS account_memory (
                account_id INTEGER PRIMARY KEY REFERENCES accounts(id),
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
                account_id INTEGER NOT NULL REFERENCES accounts(id),
                meeting_id INTEGER NOT NULL REFERENCES meeting_records(id),
                update_type TEXT NOT NULL,
                before_json TEXT NOT NULL,
                after_json TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id, meeting_id) REFERENCES meeting_records(account_id, id)
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
    with _connect(db_path) as conn:
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
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM accounts ORDER BY id ASC").fetchall()
    return [dict(row) for row in rows]


def get_account_by_id(db_path, account_id: int) -> dict | None:
    init_storage(db_path)
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
    return dict(row) if row else None


def update_account_stage_and_status(db_path, *, account_id: int, status: str, opportunity_stage: str, last_contact_at: str) -> None:
    init_storage(db_path)
    with _connect(db_path) as conn:
        cursor = conn.execute(
            """
            UPDATE accounts
            SET status = ?, opportunity_stage = ?, last_contact_at = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, opportunity_stage, last_contact_at, account_id),
        )
        if cursor.rowcount == 0:
            raise ValueError(f"Account {account_id} does not exist")
        conn.commit()


def save_meeting_record(db_path, record: dict) -> int:
    init_storage(db_path)
    with _connect(db_path) as conn:
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


def update_meeting_record(db_path, *, meeting_id: int, record: dict) -> None:
    init_storage(db_path)
    with _connect(db_path) as conn:
        cursor = conn.execute(
            """
            UPDATE meeting_records
            SET meeting_title = ?, meeting_summary_json = ?, lead_score = ?, priority = ?
            WHERE id = ?
            """,
            (
                record["meeting_title"],
                record["meeting_summary_json"],
                record["lead_score"],
                record["priority"],
                meeting_id,
            ),
        )
        if cursor.rowcount == 0:
            raise ValueError(f"Meeting {meeting_id} does not exist")
        conn.commit()


def list_meeting_records(db_path) -> list[dict]:
    init_storage(db_path)
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM meeting_records ORDER BY id ASC").fetchall()
    return [dict(row) for row in rows]


def save_task_record(db_path, record: dict) -> int:
    init_storage(db_path)
    with _connect(db_path) as conn:
        # 只把同一次 meeting 里完全相同的开放待办当成同一条，避免把不同 meeting 的任务误合并。
        if str(record.get("status", "")).strip() == "open":
            existing = conn.execute(
                """
                SELECT id
                FROM tasks
                WHERE account_id = ? AND meeting_id = ? AND title = ? AND due_at = ? AND status = 'open'
                ORDER BY id ASC
                LIMIT 1
                """,
                (
                    record["account_id"],
                    record["meeting_id"],
                    record["title"],
                    record["due_at"],
                ),
            ).fetchone()
            if existing is not None:
                return existing[0]
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


def update_task_record(db_path, *, task_id: int, record: dict) -> None:
    init_storage(db_path)
    with _connect(db_path) as conn:
        cursor = conn.execute(
            """
            UPDATE tasks
            SET description = ?, priority = ?, due_at = ?, status = ?
            WHERE id = ?
            """,
            (
                record["description"],
                record["priority"],
                record["due_at"],
                record["status"],
                task_id,
            ),
        )
        if cursor.rowcount == 0:
            raise ValueError(f"Task {task_id} does not exist")
        conn.commit()


def list_tasks(db_path) -> list[dict]:
    init_storage(db_path)
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM tasks ORDER BY id ASC").fetchall()
    return [dict(row) for row in rows]


def upsert_account_memory(db_path, account_id: int, payload: dict) -> None:
    init_storage(db_path)
    # account_memory 只保留每个账号一行，所以用主键冲突做覆盖更新最简单。
    with _connect(db_path) as conn:
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
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM account_memory WHERE account_id = ?", (account_id,)).fetchone()
    return dict(row) if row else None


def save_crm_update(db_path, payload: dict) -> int:
    init_storage(db_path)
    with _connect(db_path) as conn:
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
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM crm_updates ORDER BY id ASC").fetchall()
    return [dict(row) for row in rows]


def save_knowledge_chunk(db_path, payload: dict) -> int:
    init_storage(db_path)
    with _connect(db_path) as conn:
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
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]
