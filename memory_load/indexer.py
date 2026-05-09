"""Index Claude Code, Codex CLI, and Copilot CLI session files into ChromaDB."""

import hashlib
import json
import sqlite3
from collections.abc import Generator
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

from .config import (
    CHROMA_DIR,
    CHUNK_SIZE,
    CLAUDE_SESSIONS_DIR,
    CODEX_SESSIONS_DIR,
    COLLECTION_NAME,
    COPILOT_SESSION_DB,
    EMBED_MODEL,
)


def _get_client() -> chromadb.PersistentClient:
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


def _get_collection(client: chromadb.PersistentClient):
    return client.get_or_create_collection(COLLECTION_NAME)


def _extract_text(content) -> str:
    """Extract plain text from a message content field."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
                elif block.get("type") == "tool_result":
                    inner = block.get("content", "")
                    if isinstance(inner, str):
                        parts.append(inner)
                    elif isinstance(inner, list):
                        for ib in inner:
                            if isinstance(ib, dict) and ib.get("type") == "text":
                                parts.append(ib.get("text", ""))
        return " ".join(parts).strip()
    return ""


def _iter_turns(jsonl_path: Path) -> Generator[dict, None, None]:
    """Yield conversation turns (user + assistant pairs) from a Claude Code session file."""
    messages = []
    with open(jsonl_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") not in ("user", "assistant"):
                continue
            text = _extract_text(obj.get("message", {}).get("content", ""))
            if text:
                messages.append(
                    {
                        "role": obj["type"],
                        "text": text,
                        "timestamp": obj.get("timestamp", ""),
                        "session_id": obj.get("sessionId", ""),
                        "cwd": obj.get("cwd", ""),
                    }
                )

    # pair up user+assistant as turns
    i = 0
    while i < len(messages):
        if messages[i]["role"] == "user":
            turn = {"user": messages[i]["text"], "assistant": "", **messages[i]}
            if i + 1 < len(messages) and messages[i + 1]["role"] == "assistant":
                turn["assistant"] = messages[i + 1]["text"]
                i += 2
            else:
                i += 1
            yield turn
        else:
            i += 1


def _iter_codex_turns(jsonl_path: Path) -> Generator[dict, None, None]:
    """Yield conversation turns from a Codex CLI session JSONL file.

    Codex stores sessions as rollout-*.jsonl files under ~/.codex/sessions/YYYY/MM/DD/.
    Each line is a JSON object with ``type`` and ``payload``. We use ``response_item``
    entries (role=user/assistant) and pair them into turns, skipping duplicate
    ``event_msg`` entries and system context blocks.
    """
    session_id = jsonl_path.stem
    cwd = ""
    timestamp = ""
    messages = []

    with open(jsonl_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            entry_type = obj.get("type")
            payload = obj.get("payload", {})

            if entry_type == "session_meta":
                session_id = payload.get("id", session_id)
                cwd = payload.get("cwd", "")
                continue

            # Only process response_item; skip event_msg (duplicates) and others
            if entry_type != "response_item":
                continue

            role = payload.get("role")
            if role not in ("user", "assistant"):
                continue

            ts = obj.get("timestamp", "")

            # Extract text from content blocks
            text_parts = []
            for block in payload.get("content", []):
                if not isinstance(block, dict):
                    continue
                btype = block.get("type", "")
                if btype in ("input_text", "output_text", "text"):
                    t = block.get("text", "").strip()
                    # Skip environment context injections
                    if t and not t.startswith("<environment_context>"):
                        text_parts.append(t)

            text = " ".join(text_parts).strip()
            if text:
                messages.append(
                    {
                        "role": role,
                        "text": text,
                        "timestamp": ts or timestamp,
                        "session_id": session_id,
                        "cwd": cwd,
                    }
                )
                if ts:
                    timestamp = ts

    # pair user+assistant as turns
    i = 0
    while i < len(messages):
        if messages[i]["role"] == "user":
            turn = {"user": messages[i]["text"], "assistant": "", **messages[i]}
            if i + 1 < len(messages) and messages[i + 1]["role"] == "assistant":
                turn["assistant"] = messages[i + 1]["text"]
                i += 2
            else:
                i += 1
            yield turn
        else:
            i += 1


def _chunk(text: str, size: int = CHUNK_SIZE) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)] if text else []


def _add_chunks(
    collection,
    existing_ids: set,
    model,
    *,
    session_id: str,
    project: str,
    source: str,
    turns,
    verbose: bool = False,
) -> int:
    """Embed and upsert turn chunks. Returns number of new chunks added."""
    added = 0
    for turn_idx, turn in enumerate(turns):
        combined = f"User: {turn['user']}\nAssistant: {turn['assistant']}"
        for chunk_idx, chunk in enumerate(_chunk(combined)):
            doc_id = hashlib.md5(
                f"{source}:{session_id}:{turn_idx}:{chunk_idx}".encode()
            ).hexdigest()

            if doc_id in existing_ids:
                continue

            embedding = model.encode(chunk).tolist()
            collection.add(
                ids=[doc_id],
                documents=[chunk],
                embeddings=[embedding],
                metadatas=[
                    {
                        "source": source,
                        "project": project,
                        "session_id": session_id,
                        "timestamp": turn.get("timestamp", ""),
                        "cwd": turn.get("cwd", ""),
                        "turn_idx": turn_idx,
                        "chunk_idx": chunk_idx,
                    }
                ],
            )
            existing_ids.add(doc_id)
            added += 1
    return added


def index_sessions(sessions_dir: Path = CLAUDE_SESSIONS_DIR, verbose: bool = False) -> int:
    """Index Claude Code sessions only (backward-compatible entrypoint)."""
    model = SentenceTransformer(EMBED_MODEL)
    client = _get_client()
    collection = _get_collection(client)
    existing_ids = set(collection.get(include=[])["ids"])
    added = 0

    for project_dir in sessions_dir.iterdir():
        if not project_dir.is_dir():
            continue
        project = project_dir.name

        for jsonl_file in project_dir.glob("*.jsonl"):
            session_id = jsonl_file.stem
            added += _add_chunks(
                collection,
                existing_ids,
                model,
                session_id=session_id,
                project=project,
                source="claude",
                turns=list(_iter_turns(jsonl_file)),
                verbose=verbose,
            )
            if verbose:
                print(f"  [claude] indexed {jsonl_file.name}")

    return added


def index_codex_sessions(sessions_dir: Path = CODEX_SESSIONS_DIR, verbose: bool = False) -> int:
    """Index Codex CLI sessions from ~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl."""
    if not sessions_dir.exists():
        return 0

    model = SentenceTransformer(EMBED_MODEL)
    client = _get_client()
    collection = _get_collection(client)
    existing_ids = set(collection.get(include=[])["ids"])
    added = 0

    for jsonl_file in sessions_dir.rglob("rollout-*.jsonl"):
        # Derive a stable project name from cwd embedded in the filename path
        # (year/month/day dir structure), fall back to the file stem
        session_id = jsonl_file.stem
        turns = list(_iter_codex_turns(jsonl_file))
        if not turns:
            continue
        # Use cwd from first turn to build a project-like slug
        cwd = turns[0].get("cwd", "")
        project = cwd.replace("/", "-").lstrip("-") if cwd else "codex"
        added += _add_chunks(
            collection,
            existing_ids,
            model,
            session_id=session_id,
            project=project,
            source="codex",
            turns=turns,
            verbose=verbose,
        )
        if verbose:
            print(f"  [codex] indexed {jsonl_file.name}")

    return added


def index_copilot_sessions(db_path: Path = COPILOT_SESSION_DB, verbose: bool = False) -> int:
    """Index GitHub Copilot CLI sessions from ~/.copilot/session-store.db."""
    if not db_path.exists():
        return 0

    model = SentenceTransformer(EMBED_MODEL)
    client = _get_client()
    collection = _get_collection(client)
    existing_ids = set(collection.get(include=[])["ids"])
    added = 0

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """
            SELECT s.id as session_id, s.cwd, s.repository, s.branch,
                   t.turn_index, t.user_message, t.assistant_response, t.timestamp
            FROM sessions s
            JOIN turns t ON t.session_id = s.id
            WHERE t.user_message IS NOT NULL OR t.assistant_response IS NOT NULL
            ORDER BY s.id, t.turn_index
            """
        ).fetchall()
    finally:
        con.close()

    # Group rows by session_id
    sessions: dict[str, list] = {}
    meta: dict[str, dict] = {}
    for row in rows:
        sid = row["session_id"]
        if sid not in sessions:
            sessions[sid] = []
            cwd = row["cwd"] or ""
            repo = row["repository"] or ""
            meta[sid] = {
                "cwd": cwd,
                "project": repo.replace("/", "-") if repo else cwd.replace("/", "-").lstrip("-") or "copilot",
            }
        sessions[sid].append(
            {
                "user": (row["user_message"] or "").strip(),
                "assistant": (row["assistant_response"] or "").strip(),
                "timestamp": row["timestamp"] or "",
                "session_id": sid,
                "cwd": meta[sid]["cwd"],
            }
        )

    for sid, turns in sessions.items():
        added += _add_chunks(
            collection,
            existing_ids,
            model,
            session_id=sid,
            project=meta[sid]["project"],
            source="copilot",
            turns=turns,
            verbose=verbose,
        )
        if verbose:
            print(f"  [copilot] indexed session {sid}")

    return added


def index_all_sources(verbose: bool = False) -> dict[str, int]:
    """Index all supported sources: Claude Code, Codex CLI, Copilot CLI.

    Returns a dict with per-source chunk counts.
    """
    results = {
        "claude": index_sessions(verbose=verbose),
        "codex": index_codex_sessions(verbose=verbose),
        "copilot": index_copilot_sessions(verbose=verbose),
    }
    return results


def save_memory(text: str, tags: list[str] | None = None) -> str:
    """Manually save a piece of text as a memory."""
    model = SentenceTransformer(EMBED_MODEL)
    client = _get_client()
    collection = _get_collection(client)

    doc_id = hashlib.md5(text.encode()).hexdigest()
    embedding = model.encode(text).tolist()
    collection.add(
        ids=[doc_id],
        documents=[text],
        embeddings=[embedding],
        metadatas=[
            {
                "source": "manual",
                "project": "manual",
                "session_id": "manual",
                "timestamp": "",
                "cwd": "",
                "turn_idx": -1,
                "chunk_idx": 0,
                "tags": ",".join(tags or []),
            }
        ],
    )
    return doc_id
