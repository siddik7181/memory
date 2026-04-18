#!/usr/bin/env python3
"""memory-load CLI."""

import click

from memory_load.config import CHROMA_DIR, MEMORY_DIR
from memory_load.indexer import index_sessions, save_memory
from memory_load.knowledge_graph import (
    add_relation,
    invalidate_relation,
    kg_stats,
    list_entities,
    query_entity,
)
from memory_load.search import list_projects, search, stats


@click.group()
def cli():
    """memory-load: local semantic memory for Claude Code and other AI CLIs."""


# ── Core ─────────────────────────────────────────────────────────────────────


@cli.command()
def init():
    """Initialize memory store directories."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    click.echo(f"Initialized at {MEMORY_DIR}")


@cli.command()
@click.option("--verbose", "-v", is_flag=True)
def index(verbose):
    """Index all Claude Code session history."""
    click.echo("Indexing sessions...")
    added = index_sessions(verbose=verbose)
    click.echo(f"Done. Added {added} new chunks.")


@cli.command()
@click.argument("query_text")
@click.option("--top-k", "-k", default=5, show_default=True)
@click.option("--project", "-p", default=None, help="Filter by project name")
@click.option("--since", default=None, help="ISO 8601 lower-bound timestamp")
def query(query_text, top_k, project, since):
    """Search memories by meaning."""
    hits = search(query_text, top_k=top_k, project=project, since=since)
    if not hits:
        click.echo("No results.")
        return
    for i, h in enumerate(hits, 1):
        click.echo(f"\n[{i}] score={h['score']}  {h['project']}  {h['timestamp']}")
        click.echo(h["text"])


@cli.command()
@click.argument("text")
@click.option("--tags", default="", help="Comma-separated tags")
def save(text, tags):
    """Manually save a memory."""
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    doc_id = save_memory(text, tags=tag_list)
    click.echo(f"Saved: {doc_id}")


@cli.command()
def stat():
    """Show memory store stats."""
    s = stats()
    click.echo(f"Total chunks: {s['total_chunks']}")
    if s["projects"]:
        click.echo("Projects:")
        for p in s["projects"]:
            click.echo(f"  {p}")


@cli.command()
def projects():
    """List all indexed project names."""
    for p in list_projects():
        click.echo(p)


# ── Knowledge graph ───────────────────────────────────────────────────────────


@cli.group()
def kg():
    """Knowledge graph commands."""


@kg.command("add")
@click.argument("subject")
@click.argument("predicate")
@click.argument("object_")
@click.option("--subject-type", default="concept")
@click.option("--object-type", default="concept")
@click.option("--note", default="")
def kg_add(subject, predicate, object_, subject_type, object_type, note):
    """Add a relation: SUBJECT PREDICATE OBJECT."""
    rid = add_relation(
        subject,
        predicate,
        object_,
        subject_type=subject_type,
        object_type=object_type,
        note=note or None,
    )
    click.echo(f"Added relation id={rid}: {subject} --[{predicate}]--> {object_}")


@kg.command("query")
@click.argument("entity")
@click.option("--at", default=None, help="Point-in-time ISO 8601 timestamp")
def kg_query(entity, at):
    """Query relations for ENTITY."""
    rows = query_entity(entity, at=at)
    if not rows:
        click.echo(f"No relations found for '{entity}'.")
        return
    for r in rows:
        click.echo(f"[{r['id']}] {r['subject']} --[{r['predicate']}]--> {r['object']}")
        if r["note"]:
            click.echo(f"     note: {r['note']}")


@kg.command("invalidate")
@click.argument("relation_id", type=int)
def kg_invalidate(relation_id):
    """Expire a relation by id."""
    invalidate_relation(relation_id)
    click.echo(f"Invalidated relation id={relation_id}")


@kg.command("entities")
@click.option("--type", "entity_type", default=None)
def kg_entities(entity_type):
    """List entities in the knowledge graph."""
    entities = list_entities(entity_type=entity_type)
    if not entities:
        click.echo("No entities.")
        return
    for e in entities:
        click.echo(f"[{e['id']}] {e['name']} ({e['type']})")


@kg.command("stat")
def kg_stat():
    """Show knowledge graph stats."""
    s = kg_stats()
    click.echo(
        f"Entities: {s['entities']}  Relations: {s['relations']}  Active: {s['active_relations']}"
    )


# ── MCP server ────────────────────────────────────────────────────────────────


@cli.command()
@click.option(
    "--transport",
    default="stdio",
    type=click.Choice(["stdio", "http", "sse", "streamable-http"]),
    show_default=True,
    help="MCP transport protocol.",
)
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8765, show_default=True)
def serve(transport, host, port):
    """Start the MCP server.

    stdio          → Claude Code, Codex CLI, Gemini CLI (default)
    http           → VS Code Copilot, any HTTP MCP client
    streamable-http → modern HTTP+streaming clients
    sse            → legacy SSE clients
    """
    from memory_load.mcp_server import mcp

    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        click.echo(f"MCP server on {transport}://{host}:{port}")
        mcp.run(transport=transport, host=host, port=port)


if __name__ == "__main__":
    cli()
