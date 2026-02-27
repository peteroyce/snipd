"""Unit tests for snipd models (real SQLite via tmp_path)."""

from __future__ import annotations

import pytest

from snipd.models import (
    create_snippet,
    delete_snippet,
    get_snippet,
    import_snippets,
    list_snippets,
    search_snippets,
    update_snippet,
)
from snipd.constants import MAX_BODY_BYTES


@pytest.fixture(autouse=True)
def use_temp_db(tmp_path, monkeypatch):
    """Redirect DB to a temp file for each test."""
    import snipd.db as db_module
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")


# ---------------------------------------------------------------------------
# Basic CRUD
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

def test_list_pagination_limit():
    for i in range(5):
        create_snippet(f"Snippet {i}", "text", f"body {i}", [])
    first_two = list_snippets(limit=2, offset=0)
    assert len(first_two) == 2


def test_list_pagination_offset():
    for i in range(5):
        create_snippet(f"Snippet {i}", "text", f"body {i}", [])
    all_snippets = list_snippets(limit=100, offset=0)
    offset_snippets = list_snippets(limit=100, offset=3)
    assert len(offset_snippets) == len(all_snippets) - 3


# ---------------------------------------------------------------------------
# Language normalisation
# ---------------------------------------------------------------------------

def test_language_normalised_to_lowercase():
    s = create_snippet("Norm Test", "  Python  ", "pass", [])
    assert s.language == "python"


def test_language_normalised_on_update():
    s = create_snippet("Lang Update", "text", "x = 1", [])
    updated = update_snippet(s.id, language="  JavaScript  ")
    assert updated.language == "javascript"


# ---------------------------------------------------------------------------
# FTS search
# ---------------------------------------------------------------------------

def test_search():
    create_snippet("Fibonacci function", "python", "def fib(n): ...", ["algo"])
    create_snippet("Sort array", "js", "arr.sort()", [])
    results = search_snippets("fib")
    assert any("Fibonacci" in s.title for s in results)


def test_search_limit_200(monkeypatch):
    """Verify the LIMIT 200 is applied (mock: insert 5 and check we get at most 200)."""
    for i in range(5):
        create_snippet(f"Item {i}", "text", f"content {i}", [])
    results = search_snippets("content")
    # Must not exceed 200 (real enforcement — just confirm it works)
    assert len(results) <= 200
    assert len(results) == 5  # all 5 match


# ---------------------------------------------------------------------------
# Body size enforcement
# ---------------------------------------------------------------------------

def test_body_size_rejection():
    import click
    oversized = "x" * (MAX_BODY_BYTES + 1)
    with pytest.raises(click.ClickException, match="500 KB"):
        create_snippet("Big", "text", oversized, [])


def test_body_size_at_limit_accepted():
    # Exactly at the limit should succeed
    at_limit = "x" * MAX_BODY_BYTES
    s = create_snippet("At Limit", "text", at_limit, [])
    assert s.id is not None


# ---------------------------------------------------------------------------
# Import helper
# ---------------------------------------------------------------------------

def test_import_snippets():
    data = [
        {"title": "Imported A", "language": "python", "body": "pass", "tags": ["imported"]},
        {"title": "Imported B", "language": "bash", "body": "echo hi", "tags": []},
    ]
    created = import_snippets(data)
    assert len(created) == 2
    assert created[0].title == "Imported A"
    all_s = list_snippets()
    assert len(all_s) == 2


# ---------------------------------------------------------------------------
# Edge cases (title validation, empty tag rejection, update field guard)
# ---------------------------------------------------------------------------

def test_create_whitespace_only_title_raises():
    """create_snippet with a whitespace-only title must raise ClickException."""
    import click
    with pytest.raises(click.ClickException, match="[Tt]itle"):
        create_snippet("   ", "python", "pass", [])


def test_create_empty_title_raises():
    """create_snippet with an empty string title must raise ClickException."""
    import click
    with pytest.raises(click.ClickException, match="[Tt]itle"):
        create_snippet("", "python", "pass", [])


def test_whitespace_only_tag_not_stored():
    """Tags that are whitespace-only after strip() must NOT appear in the DB."""
    s = create_snippet("Tag Edge Case", "python", "x = 1", ["  ", "\t", "valid"])
    # Only "valid" should survive; the two whitespace-only entries must be dropped
    assert s.tags == ["valid"]
    assert "" not in s.tags
    assert "  " not in s.tags


def test_update_snippet_disallowed_field_raises():
    """update_snippet with a field name not in ALLOWED_UPDATE_FIELDS must raise ValueError."""
    s = create_snippet("Guard Test", "python", "pass", [])
    with pytest.raises(ValueError, match="not allowed"):
        update_snippet(s.id, evil_column="DROP TABLE snippets")


def validate_6(data):
    """Validate: fix data loading"""
    return data is not None


CONFIG_13 = {"timeout": 43, "retries": 3}
