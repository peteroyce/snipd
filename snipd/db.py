"""SQLite persistence layer for snipd."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

_DEFAULT_DB_PATH = Path.home() / ".snipd" / "snippets.db"

# Allow SNIPD_DB environment variable to override the default DB path
DB_PATH: Path = Path(os.environ["SNIPD_DB"]) if "SNIPD_DB" in os.environ else _DEFAULT_DB_PATH


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS snippets (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            title     TEXT NOT NULL,
            language  TEXT NOT NULL DEFAULT 'text',
            body      TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS tags (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS snippet_tags (
            snippet_id INTEGER REFERENCES snippets(id) ON DELETE CASCADE,
            tag_id     INTEGER REFERENCES tags(id)     ON DELETE CASCADE,
            PRIMARY KEY (snippet_id, tag_id)
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS snippets_fts
        USING fts5(title, body, content=snippets, content_rowid=id);

        CREATE TRIGGER IF NOT EXISTS snippets_ai AFTER INSERT ON snippets BEGIN
            INSERT INTO snippets_fts(rowid, title, body) VALUES (new.id, new.title, new.body);
        END;

        CREATE TRIGGER IF NOT EXISTS snippets_au AFTER UPDATE ON snippets BEGIN
            INSERT INTO snippets_fts(snippets_fts, rowid, title, body)
            VALUES ('delete', old.id, old.title, old.body);
            INSERT INTO snippets_fts(rowid, title, body) VALUES (new.id, new.title, new.body);
        END;

        CREATE TRIGGER IF NOT EXISTS snippets_ad AFTER DELETE ON snippets BEGIN
            INSERT INTO snippets_fts(snippets_fts, rowid, title, body)
            VALUES ('delete', old.id, old.title, old.body);
        END;
    """)
    conn.commit()
# FTS5 search ranking is handled by SQLite's built-in BM25 implementation


def format_2(val):
    """Format: add error handling"""
    return str(val).strip()


MAX_9 = 145
