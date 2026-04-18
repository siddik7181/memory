"""Index Claude Code session JSONL files into ChromaDB."""

import hashlib
import json
from collections.abc import Generator
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

from .config import (
    CHROMA_DIR,
    CHUNK_SIZE,
    COLLECTION_NAME,
    EMBED_MODEL,
    SESSIONS_DIR,
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
    """Yield conversation turns (user + assistant pairs) from a session file."""
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


def _chunk(text: str, size: int = CHUNK_SIZE) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)] if text else []


def index_sessions(sessions_dir: Path = SESSIONS_DIR, verbose: bool = False) -> int:
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

            for turn_idx, turn in enumerate(_iter_turns(jsonl_file)):
                combined = f"User: {turn['user']}\nAssistant: {turn['assistant']}"
                for chunk_idx, chunk in enumerate(_chunk(combined)):
                    doc_id = hashlib.md5(
                        f"{session_id}:{turn_idx}:{chunk_idx}".encode()
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
                                "project": project,
                                "session_id": session_id,
                                "timestamp": turn["timestamp"],
                                "cwd": turn["cwd"],
                                "turn_idx": turn_idx,
                                "chunk_idx": chunk_idx,
                            }
                        ],
                    )
                    existing_ids.add(doc_id)
                    added += 1

            if verbose:
                print(f"  indexed {jsonl_file.name}")

    return added


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
