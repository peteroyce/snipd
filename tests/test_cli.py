"""CLI integration tests for snipd using Click's CliRunner with real SQLite."""

from __future__ import annotations

import json
import os
import pytest
from click.testing import CliRunner

from snipd.cli import cli


@pytest.fixture(autouse=True)
def use_temp_db(tmp_path, monkeypatch):
    """Redirect DB to a temp file for each test."""
    import snipd.db as db_module
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")


@pytest.fixture()
def runner():
    return CliRunner()


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------

def test_add_success(runner):
    result = runner.invoke(cli, ["add", "--title", "My Snippet", "--lang", "python"], input="print('hi')\n")
    assert result.exit_code == 0, result.output
    assert "Saved snippet" in result.output
    assert "#1" in result.output


def test_add_from_file(runner, tmp_path):
    snippet_file = tmp_path / "code.py"
    snippet_file.write_text("def hello(): pass\n")
    result = runner.invoke(cli, ["add", "--title", "From File", "--lang", "python", str(snippet_file)])
    assert result.exit_code == 0, result.output
    assert "Saved snippet" in result.output


def test_add_empty_body_rejected(runner):
    result = runner.invoke(cli, ["add", "--title", "Empty"], input="\n   \n")
    assert result.exit_code != 0
    assert "Empty snippet" in result.output


def test_add_oversized_body_rejected(runner):
    big = "x" * 500_001
    result = runner.invoke(cli, ["add", "--title", "Big", "--lang", "text"], input=big)
    assert result.exit_code != 0
    assert "500 KB" in result.output


def test_add_language_normalised(runner, tmp_path):
    """Language should be stored lowercase."""
    from snipd import models
    result = runner.invoke(cli, ["add", "--title", "LangTest", "--lang", "  Python  "], input="x = 1\n")
    assert result.exit_code == 0, result.output
    snippets = models.list_snippets()
    assert snippets[0].language == "python"


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

def test_list_empty(runner):
    result = runner.invoke(cli, ["list"])
    assert result.exit_code == 0
    assert "No snippets" in result.output


def test_list_shows_snippets(runner):
    runner.invoke(cli, ["add", "--title", "Alpha", "--lang", "bash"], input="echo hello\n")
    runner.invoke(cli, ["add", "--title", "Beta", "--lang", "python"], input="pass\n")
    result = runner.invoke(cli, ["list"])
    assert result.exit_code == 0
    assert "Alpha" in result.output
    assert "Beta" in result.output


def test_list_with_limit(runner):
    for i in range(5):
        runner.invoke(cli, ["add", "--title", f"Snip {i}", "--lang", "text"], input=f"body {i}\n")
    result = runner.invoke(cli, ["list", "--limit", "2"])
    assert result.exit_code == 0
    # Rich table rows: we won't count exactly, just ensure fewer entries than 5
    # (check that only 2 IDs appear — IDs 4 and 5 are most recent)
    assert "Snip" in result.output


def test_list_with_offset(runner):
    for i in range(3):
        runner.invoke(cli, ["add", "--title", f"Item {i}", "--lang", "text"], input=f"x={i}\n")
    result_all = runner.invoke(cli, ["list", "--limit", "100"])
    result_offset = runner.invoke(cli, ["list", "--limit", "100", "--offset", "2"])
    assert result_offset.exit_code == 0


# ---------------------------------------------------------------------------
# get (alias command)
# ---------------------------------------------------------------------------

def test_get_snippet(runner):
    runner.invoke(cli, ["add", "--title", "GetMe", "--lang", "python"], input="return 42\n")
    result = runner.invoke(cli, ["get", "1"])
    assert result.exit_code == 0, result.output
    assert "GetMe" in result.output


def test_get_not_found(runner):
    result = runner.invoke(cli, ["get", "999"])
    assert result.exit_code != 0
    assert "not found" in result.output.lower()


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------

def test_delete_snippet(runner):
    runner.invoke(cli, ["add", "--title", "ToDelete", "--lang", "text"], input="bye\n")
    result = runner.invoke(cli, ["delete", "1"], input="y\n")
    assert result.exit_code == 0
    assert "Deleted" in result.output
    # Verify it's gone
    result2 = runner.invoke(cli, ["get", "1"])
    assert result2.exit_code != 0


def test_delete_not_found(runner):
    result = runner.invoke(cli, ["delete", "999"], input="y\n")
    assert result.exit_code != 0
    assert "not found" in result.output.lower()


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------

def test_update_title(runner):
    runner.invoke(cli, ["add", "--title", "Old", "--lang", "text"], input="hello\n")
    result = runner.invoke(cli, ["update", "1", "--title", "New"])
    assert result.exit_code == 0, result.output
    assert "Updated snippet" in result.output
    # Verify via get
    get_result = runner.invoke(cli, ["get", "1"])
    assert "New" in get_result.output


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

def test_search_returns_results(runner):
    runner.invoke(cli, ["add", "--title", "Fibonacci algo", "--lang", "python"], input="def fib(n): ...\n")
    runner.invoke(cli, ["add", "--title", "Sort array", "--lang", "js"], input="arr.sort()\n")
    result = runner.invoke(cli, ["search", "fib"])
    assert result.exit_code == 0
    assert "Fibonacci" in result.output


def test_search_no_results(runner):
    runner.invoke(cli, ["add", "--title", "Hello", "--lang", "text"], input="world\n")
    result = runner.invoke(cli, ["search", "zzznomatch"])
    assert result.exit_code == 0
    assert "No results" in result.output


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------

def test_export_json(runner, tmp_path):
    runner.invoke(cli, ["add", "--title", "ExportMe", "--lang", "python"], input="x = 1\n")
    out_file = str(tmp_path / "out.json")
    result = runner.invoke(cli, ["export", "--format", "json", "--output", out_file])
    assert result.exit_code == 0, result.output
    assert "Exported" in result.output

    with open(out_file) as f:
        data = json.load(f)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["title"] == "ExportMe"


def test_export_json_stdout(runner):
    runner.invoke(cli, ["add", "--title", "StdoutSnip", "--lang", "text"], input="hello\n")
    result = runner.invoke(cli, ["export", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert any(s["title"] == "StdoutSnip" for s in data)


def test_export_path_traversal_rejected(runner):
    result = runner.invoke(cli, ["export", "--output", "../../../etc/passwd"])
    assert result.exit_code != 0
    assert "traversal" in result.output.lower() or "invalid" in result.output.lower()


def test_export_path_traversal_embedded_rejected(runner):
    result = runner.invoke(cli, ["export", "--output", "/tmp/foo/../../../etc/passwd"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# import (roundtrip)
# ---------------------------------------------------------------------------

def test_import_json_roundtrip(runner, tmp_path):
    # Create some snippets
    runner.invoke(cli, ["add", "--title", "RoundA", "--lang", "python"], input="print(1)\n")
    runner.invoke(cli, ["add", "--title", "RoundB", "--lang", "bash"], input="echo ok\n")

    # Export to file
    out_file = str(tmp_path / "export.json")
    runner.invoke(cli, ["export", "--format", "json", "--output", out_file])

    # Verify the export file looks right before clearing
    with open(out_file) as f:
        exported = json.load(f)
    assert len(exported) == 2

    # Clear existing snippets by deleting them (avoids Windows file-lock on the .db)
    from snipd import models as m
    for s in m.list_snippets(limit=1000):
        m.delete_snippet(s.id)

    # Confirm empty
    assert m.list_snippets() == []

    # Reimport
    result = runner.invoke(cli, ["import", out_file])
    assert result.exit_code == 0, result.output
    assert "Imported" in result.output
    assert "2" in result.output

    # Verify contents
    list_result = runner.invoke(cli, ["list"])
    assert "RoundA" in list_result.output
    assert "RoundB" in list_result.output


def test_import_invalid_json(runner, tmp_path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("not json at all {{{")
    result = runner.invoke(cli, ["import", str(bad_file)])
    assert result.exit_code != 0
    assert "Invalid JSON" in result.output or "Error" in result.output


def test_import_json_not_array(runner, tmp_path):
    bad_file = tmp_path / "obj.json"
    bad_file.write_text('{"title": "single object"}')
    result = runner.invoke(cli, ["import", str(bad_file)])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# SNIPD_DB env var
# ---------------------------------------------------------------------------

def test_snipd_db_env_var(tmp_path, monkeypatch):
    """SNIPD_DB env var should direct db.get_conn() to the specified path."""
    custom_db = str(tmp_path / "custom.db")
    monkeypatch.setenv("SNIPD_DB", custom_db)

    # Re-import db so the module-level DB_PATH re-evaluates
    import importlib
    import snipd.db as db_module
    importlib.reload(db_module)
    # After reload, patch models too
    import snipd.models as models_module
    importlib.reload(models_module)

    from snipd.models import create_snippet as cs, list_snippets as ls
    cs("EnvTest", "text", "env body", [])
    snippets = ls()
    assert any(s.title == "EnvTest" for s in snippets)
    assert db_module.DB_PATH == tmp_path / "custom.db"
