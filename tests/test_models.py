"""Unit tests for snipd models (in-memory SQLite)."""

from __future__ import annotations

import pytest
from unittest.mock import patch
from pathlib import Path


@pytest.fixture(autouse=True)
def use_temp_db(tmp_path, monkeypatch):
    """Redirect DB to a temp file for each test."""
    import snipd.db as db_module
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")


from snipd.models import create_snippet, list_snippets, search_snippets, delete_snippet, get_snippet, update_snippet


def test_create_and_get():
    s = create_snippet("Hello World", "python", "print('hello')", ["python", "demo"])
    assert s.id is not None
    assert s.title == "Hello World"
    assert "python" in s.tags


def test_list_all():
    create_snippet("Snippet A", "bash", "echo hi", [])
    create_snippet("Snippet B", "python", "pass", ["demo"])
    snippets = list_snippets()
    assert len(snippets) == 2


def test_list_by_tag():
    create_snippet("Tagged", "js", "console.log()", ["js", "frontend"])
    create_snippet("Untagged", "text", "hello", [])
    result = list_snippets(tag="js")
    assert all("js" in s.tags for s in result)


def test_search():
    create_snippet("Fibonacci function", "python", "def fib(n): ...", ["algo"])
    create_snippet("Sort array", "js", "arr.sort()", [])
    results = search_snippets("fib")
    assert any("Fibonacci" in s.title for s in results)


def test_delete():
    s = create_snippet("To Delete", "text", "bye", [])
    assert delete_snippet(s.id) is True
    assert get_snippet(s.id) is None


def test_update():
    s = create_snippet("Old Title", "text", "old body", [])
    updated = update_snippet(s.id, title="New Title", body="new body")
    assert updated.title == "New Title"
    assert updated.body == "new body"


def test_update_tags():
    s = create_snippet("Tag Test", "python", "pass", ["old"])
    updated = update_snippet(s.id, tags=["new", "fresh"])
    assert "new" in updated.tags
    assert "old" not in updated.tags
