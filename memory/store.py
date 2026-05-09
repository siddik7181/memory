"""File-based storage backend for Claude's local memory."""

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any


class MemoryStore:
    """Persists memories to a JSON file on disk."""

    def __init__(self, path: str | None = None) -> None:
        if path is None:
            default_dir = os.path.join(os.path.expanduser("~"), ".claude_memory")
            os.makedirs(default_dir, exist_ok=True)
            path = os.path.join(default_dir, "memories.json")
        self._path = path
        self._ensure_file()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_file(self) -> None:
        if not os.path.exists(self._path):
            self._write([])

    def _read(self) -> list[dict[str, Any]]:
        with open(self._path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def _write(self, data: list[dict[str, Any]]) -> None:
        with open(self._path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, content: str, tags: list[str] | None = None) -> dict[str, Any]:
        """Append a new memory entry and return it."""
        entry: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "content": content,
            "tags": tags or [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        data = self._read()
        data.append(entry)
        self._write(data)
        return entry

    def all(self) -> list[dict[str, Any]]:
        """Return every stored memory."""
        return self._read()

    def get(self, memory_id: str) -> dict[str, Any] | None:
        """Return the memory with the given *id*, or ``None``."""
        for entry in self._read():
            if entry["id"] == memory_id:
                return entry
        return None

    def search(self, query: str) -> list[dict[str, Any]]:
        """Return memories whose content or tags contain *query* (case-insensitive)."""
        q = query.lower()
        results = []
        for entry in self._read():
            if q in entry["content"].lower() or any(
                q in tag.lower() for tag in entry["tags"]
            ):
                results.append(entry)
        return results

    def delete(self, memory_id: str) -> bool:
        """Remove the memory with *memory_id*.  Returns ``True`` on success."""
        data = self._read()
        new_data = [e for e in data if e["id"] != memory_id]
        if len(new_data) == len(data):
            return False
        self._write(new_data)
        return True

    def clear(self) -> int:
        """Delete all memories.  Returns the number of entries removed."""
        data = self._read()
        count = len(data)
        self._write([])
        return count
