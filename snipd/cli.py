"""snipd — the missing CLI for code snippets."""

from __future__ import annotations

import sys
from typing import Optional

import click
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table

from snipd import models

console = Console()


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
        body = open(file).read()
    elif not sys.stdin.isatty():
        body = sys.stdin.read()
    else:
        body = click.edit(require_save=True) or ""

    if not body.strip():
        console.print("[red]Empty snippet — aborted.[/red]")
        raise SystemExit(1)

    snippet = models.create_snippet(title=title, language=lang, body=body, tags=list(tag))
    console.print(f"[green]✓[/green] Saved snippet [bold]#{snippet.id}[/bold]: {snippet.title}")


@cli.command("list")
@click.option("--tag", "-T", help="Filter by tag")
@click.option("--lang", "-l", help="Filter by language")
def list_cmd(tag: Optional[str], lang: Optional[str]):
    """List all snippets, optionally filtered by tag or language."""
    snippets = models.list_snippets(tag=tag, language=lang)
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
        console.print(f"[red]Snippet #{snippet_id} not found.[/red]")
        raise SystemExit(1)

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
            console.print("\n[yellow]⚠ Could not copy to clipboard.[/yellow]")


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
        console.print(f"[red]Snippet #{snippet_id} not found.[/red]")
        raise SystemExit(1)


@cli.command("export")
@click.option("--format", "-f", "fmt", type=click.Choice(["json", "toml"]), default="json")
@click.option("--output", "-o", type=click.Path(), help="Output file (default: stdout)")
def export(fmt: str, output: Optional[str]):
    """Export all snippets to JSON or TOML."""
    import json
    snippets = models.list_snippets()
    data = [{"id": s.id, "title": s.title, "language": s.language, "body": s.body, "tags": s.tags} for s in snippets]

    if fmt == "json":
        out = json.dumps(data, indent=2)
    else:
        try:
            import tomllib  # noqa: F401
            lines = []
            for s in data:
                lines.append(f'[[snippet]]\nid = {s["id"]}\ntitle = "{s["title"]}"\nlanguage = "{s["language"]}"\ntags = {s["tags"]!r}\nbody = """\n{s["body"]}\n"""\n')
            out = "\n".join(lines)
        except ImportError:
            out = json.dumps(data, indent=2)

    if output:
        open(output, "w").write(out)
        console.print(f"[green]✓[/green] Exported {len(data)} snippets to {output}")
    else:
        print(out)
