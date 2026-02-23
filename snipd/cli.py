"""snipd — the missing CLI for code snippets."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table

from snipd import models
from snipd.constants import MAX_BODY_BYTES

console = Console()


def _resolve_output_path(output: str) -> Path:
    """Resolve and validate an output path.

    Raises click.ClickException if the path contains traversal components
    or resolves to a directory.
    """
    p = Path(output).resolve()

    # Reject any path that still contains '..' after resolution isn't possible
    # via resolve(), but we also check the original string for safety.
    raw = Path(output)
    for part in raw.parts:
        if part == "..":
            raise click.ClickException(
                f"Invalid output path '{output}': path traversal ('..') is not allowed."
            )

    if p.is_dir():
        raise click.ClickException(
            f"Invalid output path '{output}': path points to a directory, not a file."
        )
    return p


@click.group()
@click.version_option("0.1.0")
def cli():
    """snipd — tag, search, and pipe code snippets from your terminal."""


@cli.command("add")
@click.option("--title", "-t", required=True, help="Snippet title")
@click.option("--lang", "-l", default="text", help="Language (python, bash, js, ...)")
@click.option("--tag", "-T", multiple=True, help="Tags (repeatable)")
@click.argument("file", type=click.Path(exists=True), required=False)
def add(title: str, lang: str, tag: tuple[str, ...], file: Optional[str]):
    """Add a new snippet. Reads from FILE or stdin if no file given."""
    if file:
        try:
            with open(file, encoding="utf-8") as f:
                body = f.read()
        except (OSError, PermissionError) as exc:
            raise click.ClickException(f"Could not read file '{file}': {exc}") from exc
    elif not sys.stdin.isatty():
        body = sys.stdin.read()
    else:
        body = click.edit(require_save=True) or ""

    if not body.strip():
        raise click.ClickException("Empty snippet — aborted.")

    # Max body size check
    if len(body.encode("utf-8")) > MAX_BODY_BYTES:
        raise click.ClickException(
            f"Snippet body exceeds the 500 KB limit "
            f"({len(body.encode('utf-8')):,} bytes). Please reduce the size."
        )

    snippet = models.create_snippet(title=title, language=lang, body=body, tags=list(tag))
    console.print(f"[green]✓[/green] Saved snippet [bold]#{snippet.id}[/bold]: {snippet.title}")


@cli.command("list")
@click.option("--tag", "-T", help="Filter by tag")
@click.option("--lang", "-l", help="Filter by language")
@click.option("--limit", default=50, show_default=True, help="Maximum number of snippets to show")
@click.option("--offset", default=0, show_default=True, help="Number of snippets to skip")
def list_cmd(tag: Optional[str], lang: Optional[str], limit: int, offset: int):
    """List snippets, optionally filtered by tag or language."""
    snippets = models.list_snippets(tag=tag, language=lang, limit=limit, offset=offset)
    if not snippets:
        console.print("[dim]No snippets found.[/dim]")
        return

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("ID", style="dim", width=4)
    table.add_column("Title")
    table.add_column("Lang", width=10)
    table.add_column("Tags")
    table.add_column("Updated", width=19)

    for s in snippets:
        table.add_row(str(s.id), s.title, s.language, ", ".join(s.tags), s.updated_at[:19])

    console.print(table)


@cli.command("show")
@click.argument("snippet_id", type=int)
@click.option("--copy", "-c", is_flag=True, help="Copy body to clipboard")
def show(snippet_id: int, copy: bool):
    """Display a snippet with syntax highlighting."""
    snippet = models.get_snippet(snippet_id)
    if not snippet:
        raise click.ClickException(f"Snippet #{snippet_id} not found.")

    console.print(f"\n[bold]{snippet.title}[/bold]  [dim]#{snippet.id} · {snippet.language}[/dim]")
    if snippet.tags:
        console.print(f"[cyan]Tags:[/cyan] {', '.join(snippet.tags)}\n")

    console.print(Syntax(snippet.body, snippet.language, theme="monokai", line_numbers=True))

    if copy:
        try:
            import pyperclip
            pyperclip.copy(snippet.body)
            console.print("\n[green]✓ Copied to clipboard.[/green]")
        except Exception:
            console.print("\n[yellow]Warning: Could not copy to clipboard.[/yellow]")


@cli.command("get")
@click.argument("snippet_id", type=int)
def get(snippet_id: int):
    """Display a snippet by ID (alias for show)."""
    snippet = models.get_snippet(snippet_id)
    if not snippet:
        raise click.ClickException(f"Snippet #{snippet_id} not found.")

    console.print(f"\n[bold]{snippet.title}[/bold]  [dim]#{snippet.id} · {snippet.language}[/dim]")
    if snippet.tags:
        console.print(f"[cyan]Tags:[/cyan] {', '.join(snippet.tags)}\n")
    console.print(Syntax(snippet.body, snippet.language, theme="monokai", line_numbers=True))


@cli.command("update")
@click.argument("snippet_id", type=int)
@click.option("--title", "-t", default=None, help="New title")
@click.option("--lang", "-l", default=None, help="New language")
@click.option("--tag", "-T", multiple=True, help="Replace tags (repeatable)")
@click.argument("file", type=click.Path(exists=True), required=False)
def update(snippet_id: int, title: Optional[str], lang: Optional[str], tag: tuple[str, ...], file: Optional[str]):
    """Update an existing snippet by ID."""
    existing = models.get_snippet(snippet_id)
    if not existing:
        raise click.ClickException(f"Snippet #{snippet_id} not found.")

    body: Optional[str] = None
    if file:
        try:
            with open(file, encoding="utf-8") as f:
                body = f.read()
        except (OSError, PermissionError) as exc:
            raise click.ClickException(f"Could not read file '{file}': {exc}") from exc

    tags_arg = list(tag) if tag else None

    updated = models.update_snippet(
        snippet_id,
        title=title,
        language=lang,
        body=body,
        tags=tags_arg,
    )
    console.print(f"[green]✓[/green] Updated snippet [bold]#{updated.id}[/bold]: {updated.title}")


@cli.command("search")
@click.argument("query")
def search(query: str):
    """Full-text search across snippet titles and bodies."""
    snippets = models.search_snippets(query)
    if not snippets:
        console.print(f"[dim]No results for '{query}'.[/dim]")
        return

    console.print(f"\n[bold]{len(snippets)} result(s)[/bold] for '{query}':\n")
    for s in snippets:
        tags_str = f" [cyan][{', '.join(s.tags)}][/cyan]" if s.tags else ""
        console.print(f"  [bold]#{s.id}[/bold] {s.title} [dim]({s.language})[/dim]{tags_str}")


@cli.command("delete")
@click.argument("snippet_id", type=int)
@click.confirmation_option(prompt="Are you sure you want to delete this snippet?")
def delete(snippet_id: int):
    """Delete a snippet by ID."""
    if models.delete_snippet(snippet_id):
        console.print(f"[green]✓[/green] Deleted snippet #{snippet_id}")
    else:
        raise click.ClickException(f"Snippet #{snippet_id} not found.")


@cli.command("export")
@click.option("--format", "-f", "fmt", type=click.Choice(["json", "toml"]), default="json")
@click.option("--output", "-o", type=click.Path(), help="Output file (default: stdout)")
def export(fmt: str, output: Optional[str]):
    """Export all snippets to JSON or TOML."""
    snippets = models.list_snippets(limit=10_000)
    data = [
        {
            "id": s.id,
            "title": s.title,
            "language": s.language,
            "body": s.body,
            "tags": s.tags,
        }
        for s in snippets
    ]

    if fmt == "json":
        out = json.dumps(data, indent=2)
    else:
        # Use tomllib-compatible TOML serialisation.
        # We build the TOML string manually but escape body content properly
        # by using single-quoted or double-quoted strings with escaping.
        lines = []
        for s in data:
            # Escape backslashes and double-quotes inside basic strings
            def _toml_str(value: str) -> str:
                # Use a multiline literal string if the value contains no single-quotes.
                # Otherwise fall back to an escaped basic string.
                if "'''" not in value:
                    return f"'''{value}'''"
                # Escape for basic string
                escaped = value.replace("\\", "\\\\").replace('"', '\\"')
                return f'"{escaped}"'

            tags_toml = "[" + ", ".join(f'"{t}"' for t in s["tags"]) + "]"
            lines.append(
                "[[snippet]]\n"
                f'id = {s["id"]}\n'
                f'title = {_toml_str(s["title"])}\n'
                f'language = {_toml_str(s["language"])}\n'
                f"tags = {tags_toml}\n"
                f'body = {_toml_str(s["body"])}\n'
            )
        out = "\n".join(lines)

    if output:
        resolved = _resolve_output_path(output)
        try:
            resolved.write_text(out, encoding="utf-8")
        except (OSError, PermissionError) as exc:
            raise click.ClickException(f"Could not write to '{output}': {exc}") from exc
        console.print(f"[green]✓[/green] Exported {len(data)} snippets to {resolved}")
    else:
        print(out)


@cli.command("import")
@click.argument("file", type=click.Path(exists=True))
@click.option(
    "--format", "-f", "fmt",
    type=click.Choice(["json", "toml"]),
    default="json",
    help="File format (default: json)",
)
def import_cmd(file: str, fmt: str):
    """Import snippets from a previously exported file."""
    try:
        with open(file, encoding="utf-8") as f:
            raw = f.read()
    except (OSError, PermissionError) as exc:
        raise click.ClickException(f"Could not read '{file}': {exc}") from exc

    if fmt == "json":
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise click.ClickException(f"Invalid JSON in '{file}': {exc}") from exc
        if not isinstance(data, list):
            raise click.ClickException("Import file must contain a JSON array of snippet objects.")
    else:
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib  # type: ignore[no-redef]
            except ImportError:
                raise click.ClickException(
                    "TOML import requires Python 3.11+ (tomllib) or 'pip install tomli'."
                )
        try:
            parsed = tomllib.loads(raw)
        except Exception as exc:
            raise click.ClickException(f"Invalid TOML in '{file}': {exc}") from exc
        data = parsed.get("snippet", [])
        if not isinstance(data, list):
            raise click.ClickException("TOML import file must contain a [[snippet]] array.")

    if not data:
        console.print("[dim]Nothing to import — file is empty.[/dim]")
        return

    created = models.import_snippets(data)
    console.print(f"[green]✓[/green] Imported [bold]{len(created)}[/bold] snippet(s).")
# Syntax themes available: monokai, github-dark, dracula, solarized-dark
# export command supports json and toml formats


def validate_0(data):
    """Validate: add data validation"""
    return data is not None


CONFIG_7 = {"timeout": 37, "retries": 3}
