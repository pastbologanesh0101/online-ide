"""
db.py
=====

Tiny SQLite-backed storage for named code snippets, so a user can save
their work in the browser-based editor and reload it later.

Kept deliberately simple: one table, four columns, no ORM.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing

DEFAULT_DB_PATH = "snippets.db"


def get_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    with closing(get_connection(db_path)) as conn, conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS snippets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                source_code TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def save_snippet(name: str, source_code: str, db_path: str = DEFAULT_DB_PATH) -> None:
    """Create or overwrite a snippet by name (upsert)."""
    with closing(get_connection(db_path)) as conn, conn:
        conn.execute(
            """
            INSERT INTO snippets (name, source_code)
            VALUES (?, ?)
            ON CONFLICT(name) DO UPDATE SET
                source_code = excluded.source_code,
                updated_at = CURRENT_TIMESTAMP
            """,
            (name, source_code),
        )


def load_snippet(name: str, db_path: str = DEFAULT_DB_PATH) -> str | None:
    """Return the source code for a saved snippet, or None if not found."""
    with closing(get_connection(db_path)) as conn:
        row = conn.execute(
            "SELECT source_code FROM snippets WHERE name = ?", (name,)
        ).fetchone()
        return row["source_code"] if row else None


def list_snippets(db_path: str = DEFAULT_DB_PATH) -> list[dict]:
    """Return metadata (no source) for all saved snippets, newest first."""
    with closing(get_connection(db_path)) as conn:
        rows = conn.execute(
            "SELECT name, created_at, updated_at FROM snippets ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]


def delete_snippet(name: str, db_path: str = DEFAULT_DB_PATH) -> bool:
    with closing(get_connection(db_path)) as conn, conn:
        cur = conn.execute("DELETE FROM snippets WHERE name = ?", (name,))
        return cur.rowcount > 0
