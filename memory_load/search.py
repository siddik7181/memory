"""Semantic search over indexed memories."""

import chromadb
from sentence_transformers import SentenceTransformer

from .config import CHROMA_DIR, COLLECTION_NAME, EMBED_MODEL, TOP_K


def _get_collection():
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(COLLECTION_NAME)


def search(
    query: str,
    top_k: int = TOP_K,
    project: str | None = None,
    since: str | None = None,
) -> list[dict]:
    """Return top_k relevant memory chunks for query.

    Args:
        query: Natural language query.
        top_k: Max results.
        project: Filter by project directory name (e.g. '-Users-abu-siddik-spikes').
        since: ISO 8601 timestamp lower bound (e.g. '2026-01-01T00:00:00.000Z').
    """
    model = SentenceTransformer(EMBED_MODEL)
    collection = _get_collection()

    total = collection.count()
    if total == 0:
        return []

    where_clauses = []
    if project:
        where_clauses.append({"project": {"$eq": project}})
    if since:
        where_clauses.append({"timestamp": {"$gte": since}})

    if len(where_clauses) == 1:
        where = where_clauses[0]
    elif len(where_clauses) > 1:
        where = {"$and": where_clauses}
    else:
        where = None

    embedding = model.encode(query).tolist()

    results = collection.query(
        query_embeddings=[embedding],
        n_results=min(top_k, total),
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    hits = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        hits.append(
            {
                "text": doc,
                "score": round(1 - dist, 4),
                "project": meta.get("project"),
                "session_id": meta.get("session_id"),
                "timestamp": meta.get("timestamp"),
                "cwd": meta.get("cwd"),
            }
        )

    return hits


def list_projects() -> list[str]:
    """Return distinct project names in the index."""
    collection = _get_collection()
    all_meta = collection.get(include=["metadatas"])["metadatas"]
    return sorted({m.get("project", "") for m in all_meta if m.get("project")})


def stats() -> dict:
    collection = _get_collection()
    count = collection.count()
    projects = list_projects()
    return {"total_chunks": count, "projects": projects}
