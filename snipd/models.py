"""CRUD operations for snippets and tags."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional

import click

from snipd.db import get_conn

MAX_BODY_BYTES = 500_000  # 500 KB


@dataclass
class Snippet:
    id: int
    title: str
    language: str
    body: str
    tags: list[str]
    created_at: str
    updated_at: str


def _validate_body(body: str) -> None:
    """Raise a Click error if the body exceeds the maximum allowed size."""
    if len(body.encode("utf-8")) > MAX_BODY_BYTES:
        raise click.ClickException(
            f"Snippet body exceeds the 500 KB limit "
            f"({len(body.encode('utf-8')):,} bytes). Please reduce the size."
        )


def create_snippet(title: str, language: str, body: str, tags: list[str]) -> Snippet:
    # Normalize language: lowercase + strip whitespace
    language = language.strip().lower()
    _validate_body(body)
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO snippets (title, language, body) VALUES (?, ?, ?)",
            (title, language, body),
        )
        snippet_id = cur.lastrowid
        _set_tags(conn, snippet_id, tags)
        conn.commit()
    return get_snippet(snippet_id)


def get_snippet(snippet_id: int) -> Optional[Snippet]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM snippets WHERE id = ?", (snippet_id,)).fetchone()
        if not row:
            return None
        tags = _get_tags(conn, snippet_id)
        return _row_to_snippet(row, tags)


def list_snippets(
    tag: Optional[str] = None,
    language: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Snippet]:
    with get_conn() as conn:
        query = "SELECT s.* FROM snippets s"
        params: list = []
        if tag:
            query += (
                " JOIN snippet_tags st ON s.id = st.snippet_id"
                " JOIN tags t ON st.tag_id = t.id WHERE t.name = ?"
            )
            params.append(tag)
        elif language:
            query += " WHERE s.language = ?"
            params.append(language)
        query += " ORDER BY s.updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = conn.execute(query, params).fetchall()
        return [_row_to_snippet(r, _get_tags(conn, r["id"])) for r in rows]


def search_snippets(query: str) -> list[Snippet]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT s.* FROM snippets s"
            " JOIN snippets_fts fts ON s.id = fts.rowid"
            " WHERE snippets_fts MATCH ? ORDER BY rank LIMIT 200",
            (query,),
        ).fetchall()
        return [_row_to_snippet(r, _get_tags(conn, r["id"])) for r in rows]


def delete_snippet(snippet_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM snippets WHERE id = ?", (snippet_id,))
        conn.commit()
        return cur.rowcount > 0


def update_snippet(snippet_id: int, **kwargs) -> Optional[Snippet]:
    allowed = {"title", "language", "body"}
    fields = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    # Normalize language if being updated
    if "language" in fields:
        fields["language"] = fields["language"].strip().lower()
    # Validate body size if being updated
    if "body" in fields:
        _validate_body(fields["body"])

    tags_provided = "tags" in kwargs and kwargs["tags"] is not None

    # Nothing to update at all
    if not fields and not tags_provided:
        return get_snippet(snippet_id)

    with get_conn() as conn:
        if fields:
            set_clause = ", ".join(f"{k} = ?" for k in fields)
            conn.execute(
                f"UPDATE snippets SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                [*fields.values(), snippet_id],
            )
        if tags_provided:
            _set_tags(conn, snippet_id, kwargs["tags"])
        conn.commit()
    return get_snippet(snippet_id)


def import_snippets(data: list[dict]) -> list[Snippet]:
    """Import a list of snippet dicts (from an export file). Returns created Snippets."""
    created = []
    for item in data:
        s = create_snippet(
            title=item["title"],
            language=item.get("language", "text"),
            body=item["body"],
            tags=item.get("tags", []),
        )
        created.append(s)
    return created


def _set_tags(conn: sqlite3.Connection, snippet_id: int, tags: list[str]) -> None:
    conn.execute("DELETE FROM snippet_tags WHERE snippet_id = ?", (snippet_id,))
    for tag in tags:
        tag = tag.lower().strip()
        conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag,))
        tag_id = conn.execute("SELECT id FROM tags WHERE name = ?", (tag,)).fetchone()["id"]
        conn.execute("INSERT OR IGNORE INTO snippet_tags VALUES (?, ?)", (snippet_id, tag_id))


def _get_tags(conn: sqlite3.Connection, snippet_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT t.name FROM tags t JOIN snippet_tags st ON t.id = st.tag_id WHERE st.snippet_id = ?",
        (snippet_id,),
    ).fetchall()
    return [r["name"] for r in rows]


def _row_to_snippet(row: sqlite3.Row, tags: list[str]) -> Snippet:
    return Snippet(
        id=row["id"], title=row["title"], language=row["language"],
        body=row["body"], tags=tags, created_at=row["created_at"], updated_at=row["updated_at"],
    )
# Tag normalisation: lowercase + strip enforced at write time
# Note: empty query returns all snippets ordered by recency
