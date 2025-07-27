# snipd

> The missing CLI for developers tired of Googling the same boilerplate. Tag, search, and pipe code snippets straight from your terminal.

## Install

```bash
pip install snipd
# or from source:
git clone https://github.com/peteroyce/snipd
cd snipd && pip install -e .
```

## Usage

```bash
# Add a snippet from a file
snipd add --title "JWT middleware" --lang python --tag auth --tag backend auth.py

# Add from stdin
cat my_script.sh | snipd add --title "Deploy script" --lang bash --tag devops

# List all snippets
snipd list

# Filter by tag
snipd list --tag python

# Full-text search
snipd search "jwt token"

# Show with syntax highlighting + copy to clipboard
snipd show 3 --copy

# Export to JSON
snipd export --format json --output snippets.json

# Delete
snipd delete 3
```

## Features

- **Full-text search** powered by SQLite FTS5 — instant results across titles and bodies
- **Rich terminal UI** — syntax-highlighted previews with `rich`
- **Tag system** — organise snippets with multiple tags, filter by tag or language
- **Clipboard support** — `--copy` flag pipes directly to your clipboard
- **Export/import** — JSON and TOML export for backup or sharing
- **Zero cloud** — all data lives in `~/.snipd/snippets.db`

## Tech Stack

Python · Click · Rich · SQLite (FTS5) · pyperclip
