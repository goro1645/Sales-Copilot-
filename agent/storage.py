"""负责把 Agent 结果保存到 SQLite。

这个文件的职责很单纯：
- 建表
- 插入记录
- 查询记录

把数据库逻辑单独放出来，能避免这些 SQL 语句散落在页面代码里。
"""

import sqlite3
from pathlib import Path


def init_storage(db_path) -> None:
    """初始化 SQLite 存储。

    第一次运行时，如果数据库文件或表还不存在，这里会自动创建。
    所以调用方不用手动“先建库再运行”。
    """

    db_path = Path(db_path)
    # 先保证数据库所在目录存在，否则 sqlite3 无法创建文件。
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
    """保存一条申请记录，并返回数据库自动生成的 id。"""

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
        # lastrowid 就是这次 INSERT 进去后数据库分配给它的主键。
        return cursor.lastrowid


def list_application_records(db_path) -> list[dict]:
    """读取所有历史申请记录，供网页和测试使用。"""

    init_storage(db_path)
    with sqlite3.connect(db_path) as conn:
        # 打开 row_factory 后，每一行都能像 dict 一样按字段名访问。
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, company, role, match_score, status, resume_version, cover_letter, created_at
            FROM applications
            ORDER BY id ASC
            """
        ).fetchall()
    return [dict(row) for row in rows]
