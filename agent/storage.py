import sqlite3
from pathlib import Path


def init_storage(db_path) -> None:
    """Create the SQLite database and table if they do not exist yet."""

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company TEXT NOT NULL,
                role TEXT NOT NULL,
                match_score INTEGER NOT NULL,
                status TEXT NOT NULL,
                resume_version TEXT NOT NULL,
                cover_letter TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def save_application_record(db_path, record: dict) -> int:
    """Persist one agent result and return the generated row id."""

    init_storage(db_path)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO applications (company, role, match_score, status, resume_version, cover_letter)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                record["company"],
                record["role"],
                record["match_score"],
                record["status"],
                record["resume_version"],
                record["cover_letter"],
            ),
        )
        conn.commit()
        return cursor.lastrowid


def list_application_records(db_path) -> list[dict]:
    """Return all saved applications as dictionaries for tests and demos."""

    init_storage(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, company, role, match_score, status, resume_version, cover_letter, created_at
            FROM applications
            ORDER BY id ASC
            """
        ).fetchall()
    return [dict(row) for row in rows]
