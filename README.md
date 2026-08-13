# snipd

A local-first CLI for storing, tagging and retrieving code snippets. Everything lives in a single
SQLite database in your home directory, with full-text search over titles and bodies, so the
snippets you keep re-writing are one command away instead of one search engine away.

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## Features

- Full-text search backed by SQLite FTS5, with results ranked by SQLite's built-in BM25 (`ORDER BY rank`)
- The FTS index is kept in sync by SQL triggers on insert, update and delete rather than by application
  code, so the index cannot drift if a write path is added later
- Many-to-many tags, normalised to lowercase and trimmed at write time so `Auth`, `auth ` and `AUTH`
  never become three separate tags
- Syntax-highlighted display and tabular listings via `rich`, with optional clipboard copy (`--copy`)
- Round-trip export and import in JSON or TOML, for backup or moving a snippet store between machines
- Snippet bodies are capped at 500 KB (`snipd/constants.py`) to keep the store a snippet store, not a file store
- No network access and no accounts — data is written to `~/.snipd/snippets.db`, overridable with `SNIPD_DB`
- `UPDATE` column names come from a fixed whitelist mapping rather than interpolated keyword arguments,
  so no caller can inject a column name into the SQL

## Architecture

```
 cli.py            models.py                db.py
 ────────          ──────────               ─────
 Click commands →  CRUD + validation    →   get_conn()
 Rich rendering    tag normalisation        schema bootstrap (idempotent)
                   body size limit          WAL journal mode
                                            ┌──────────────────────────┐
                                            │ snippets                 │
                                            │ tags                     │
                                            │ snippet_tags  (join)     │
                                            │ snippets_fts  (FTS5)     │
                                            │  ↑ kept current by       │
                                            │    AI / AU / AD triggers │
                                            └──────────────────────────┘
```

| Module | Responsibility |
|---|---|
| `snipd/cli.py` | Click command group, Rich output, export/import serialisation, output-path validation |
| `snipd/models.py` | `Snippet` dataclass and all CRUD; enforces title, body size and tag rules |
| `snipd/db.py` | Connection factory, DB path resolution, schema and FTS trigger creation |
| `snipd/constants.py` | `MAX_BODY_BYTES` |

The schema is created on every connection with `CREATE TABLE IF NOT EXISTS`, so there is no migration
step and no first-run command — the first write creates the database.

## Quickstart

Requires Python 3.11 or newer.

```bash
git clone https://github.com/peteroyce/snipd
cd snipd
pip install -e .
```

Optional environment variable:

| Variable | Effect |
|---|---|
| `SNIPD_DB` | Absolute path to the SQLite file. Defaults to `~/.snipd/snippets.db`. Read once at import. |

## Usage

```bash
# Add from a file
snipd add --title "JWT middleware" --lang python --tag auth --tag backend auth.py

# Add from stdin
cat deploy.sh | snipd add --title "Deploy script" --lang bash --tag devops

# With no file and no piped stdin, $EDITOR opens for you to type the body
snipd add --title "Scratch note"

snipd list                      # 50 most recently updated
snipd list --tag auth           # filter by tag
snipd list --lang python        # filter by language
snipd list --limit 10 --offset 20

snipd search "jwt token"        # FTS5 query across titles and bodies
snipd show 3 --copy             # highlighted output, body to clipboard
snipd get 3                     # same output, without the clipboard flag

snipd update 3 --title "JWT middleware (v2)" --tag auth new_body.py
snipd delete 3                  # prompts for confirmation

snipd export --format json --output snippets.json
snipd export --format toml      # to stdout if --output is omitted
snipd import snippets.json
snipd import snippets.toml --format toml
```

### Commands

| Command | Arguments and options | Notes |
|---|---|---|
| `add` | `[FILE]`, `--title/-t` (required), `--lang/-l`, `--tag/-T` (repeatable) | Body from FILE, stdin, or `$EDITOR` |
| `list` | `--tag/-T`, `--lang/-l`, `--limit`, `--offset` | `--tag` takes precedence if both filters are given |
| `show` | `SNIPPET_ID`, `--copy/-c` | Clipboard failure degrades to a warning, not an error |
| `get` | `SNIPPET_ID` | `show` without clipboard support |
| `update` | `SNIPPET_ID`, `[FILE]`, `--title`, `--lang`, `--tag` | `--tag` replaces the whole tag set |
| `search` | `QUERY` | FTS5 MATCH syntax, capped at 200 results |
| `delete` | `SNIPPET_ID` | Confirmation prompt |
| `export` | `--format json\|toml`, `--output` | Rejects `..` in the output path and refuses to write over a directory |
| `import` | `FILE`, `--format json\|toml` | TOML import needs `tomllib` (3.11+) or `tomli` |

Export and import are deliberately symmetric: `export --format toml` emits an array of `[[snippet]]`
tables that `import --format toml` reads back. Imported snippets are created fresh, so IDs in the file
are not honoured.

## Tech stack

Python 3.11+ · Click · Rich · pyperclip · SQLite with FTS5 (standard library) · pytest

## Testing

```bash
pip install -e ".[dev]"
pytest
pytest --cov=snipd --cov-report=term-missing
```

`tests/test_cli.py` drives the real command group through Click's `CliRunner` against a temporary
SQLite file, so the tests exercise the actual SQL rather than a mocked layer. GitHub Actions runs
`pytest tests/ -v` on Python 3.11 for pushes and pull requests to `main` and `master`
(`.github/workflows/ci.yml`).

## License

MIT
