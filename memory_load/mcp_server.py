"""MCP server exposing memory tools to Claude Code and other AI CLIs."""

from fastmcp import FastMCP

from .indexer import index_all_sources
from .indexer import save_memory as _save
from .knowledge_graph import (
    add_relation,
    invalidate_relation,
    kg_stats,
    list_entities,
    query_entity,
)
from .search import list_projects
from .search import search as _search
from .search import stats as _stats

mcp = FastMCP("memory-load")


# ── Semantic memory ──────────────────────────────────────────────────────────


@mcp.tool()
def memory_search(
    query: str,
    top_k: int = 5,
    project: str = "",
    since: str = "",
    source: str = "",
) -> str:
    """Search past conversations and saved memories by meaning.

    Args:
        query: What to search for.
        top_k: Number of results to return (default 5).
        project: Filter to a specific project name (optional).
        since: Only return memories after this ISO 8601 timestamp (optional).
        source: Filter by source CLI — 'claude', 'codex', 'copilot', or 'manual' (optional).
    """
    hits = _search(
        query,
        top_k=top_k,
        project=project or None,
        since=since or None,
        source=source or None,
    )
    if not hits:
        return "No relevant memories found."

    lines = []
    for i, h in enumerate(hits, 1):
        lines.append(
            f"[{i}] score={h['score']}  source={h.get('source','')}  project={h['project']}  {h['timestamp']}\n{h['text']}"
        )
    return "\n\n".join(lines)


@mcp.tool()
def memory_save(text: str, tags: str = "") -> str:
    """Save a piece of text as a permanent memory.

    Args:
        text: The text to remember.
        tags: Comma-separated tags (optional).
    """
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    doc_id = _save(text, tags=tag_list)
    return f"Saved memory (id={doc_id})"


@mcp.tool()
def memory_index() -> str:
    """Re-index all AI CLI session history (Claude Code, Codex CLI, Copilot CLI)."""
    results = index_all_sources(verbose=False)
    total = sum(results.values())
    lines = [f"  {src}: +{count} chunks" for src, count in results.items()]
    return f"Indexed {total} new chunks total.\n" + "\n".join(lines)


@mcp.tool()
def memory_stats() -> str:
    """Return stats about the memory store."""
    s = _stats()
    projects = ", ".join(s["projects"]) or "none"
    sources = ", ".join(s.get("sources", [])) or "none"
    return f"Total chunks: {s['total_chunks']}\nSources: {sources}\nProjects: {projects}"


@mcp.tool()
def memory_list_projects() -> str:
    """List all project names in the memory index."""
    projects = list_projects()
    return "\n".join(projects) if projects else "No projects indexed yet."


# ── Knowledge graph ──────────────────────────────────────────────────────────


@mcp.tool()
def kg_add_relation(
    subject: str,
    predicate: str,
    object: str,
    subject_type: str = "concept",
    object_type: str = "concept",
    note: str = "",
) -> str:
    """Add a relationship between two entities in the knowledge graph.

    Example: kg_add_relation("Python", "used_for", "backend services")

    Args:
        subject: Source entity name.
        predicate: Relationship label (e.g. 'uses', 'depends_on', 'is_a').
        object: Target entity name.
        subject_type: Entity type for subject (default 'concept').
        object_type: Entity type for object (default 'concept').
        note: Optional note about this relation.
    """
    rid = add_relation(
        subject,
        predicate,
        object,
        subject_type=subject_type,
        object_type=object_type,
        note=note or None,
    )
    return f"Added relation id={rid}: {subject} --[{predicate}]--> {object}"


@mcp.tool()
def kg_query(entity: str, at: str = "") -> str:
    """Query all relations for an entity in the knowledge graph.

    Args:
        entity: Entity name to look up.
        at: Point-in-time ISO 8601 timestamp (default: now).
    """
    rows = query_entity(entity, at=at or None)
    if not rows:
        return f"No relations found for '{entity}'."
    lines = [f"{r['subject']} --[{r['predicate']}]--> {r['object']}  (id={r['id']})" for r in rows]
    return "\n".join(lines)


@mcp.tool()
def kg_invalidate(relation_id: int) -> str:
    """Invalidate (expire) a knowledge graph relation by id.

    Args:
        relation_id: The relation id to invalidate (get from kg_query).
    """
    invalidate_relation(relation_id)
    return f"Invalidated relation id={relation_id}"


@mcp.tool()
def kg_list_entities(entity_type: str = "") -> str:
    """List entities in the knowledge graph.

    Args:
        entity_type: Filter by type (optional).
    """
    entities = list_entities(entity_type=entity_type or None)
    if not entities:
        return "No entities found."
    return "\n".join(f"[{e['id']}] {e['name']} ({e['type']})" for e in entities)


@mcp.tool()
def kg_stats_tool() -> str:
    """Return knowledge graph statistics."""
    s = kg_stats()
    return (
        f"Entities: {s['entities']}  Relations: {s['relations']}  Active: {s['active_relations']}"
    )


if __name__ == "__main__":
    mcp.run()
