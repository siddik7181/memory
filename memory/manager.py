"""High-level memory manager used by Claude (or any caller)."""

from typing import Any

from .store import MemoryStore


class MemoryManager:
    """Provides a simple interface for storing and retrieving local memories.

    Example usage::

        from memory import MemoryManager

        mgr = MemoryManager()
        mgr.remember("The user's name is Alice.")
        mgr.remember("Alice prefers dark mode.", tags=["preferences"])

        results = mgr.recall("name")
        for m in results:
            print(m["content"])
    """

    def __init__(self, store_path: str | None = None) -> None:
        """Create a manager backed by a :class:`MemoryStore`.

        Parameters
        ----------
        store_path:
            Path to the JSON file used for persistence.  When omitted the
            default location ``~/.claude_memory/memories.json`` is used.
        """
        self._store = MemoryStore(path=store_path)

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def remember(self, content: str, tags: list[str] | None = None) -> dict[str, Any]:
        """Store a new memory and return the created entry.

        Parameters
        ----------
        content:
            The text to remember.
        tags:
            Optional list of labels attached to the memory for easier recall.
        """
        return self._store.add(content, tags=tags)

    def recall(self, query: str) -> list[dict[str, Any]]:
        """Return memories that match *query*.

        The search is case-insensitive and checks both the memory content and
        any associated tags.
        """
        return self._store.search(query)

    def forget(self, memory_id: str) -> bool:
        """Delete the memory identified by *memory_id*.

        Returns ``True`` if the memory was found and removed, ``False``
        otherwise.
        """
        return self._store.delete(memory_id)

    def all_memories(self) -> list[dict[str, Any]]:
        """Return a list of all stored memories."""
        return self._store.all()

    def clear_all(self) -> int:
        """Remove every stored memory and return the count of deleted entries."""
        return self._store.clear()

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def format_for_context(self) -> str:
        """Return all memories formatted as a system-prompt-ready string.

        The output is suitable for injecting into a Claude (or any LLM) system
        prompt so the model is aware of stored facts.
        """
        memories = self._store.all()
        if not memories:
            return ""
        lines = ["[Memories]"]
        for entry in memories:
            tag_str = f" [{', '.join(entry['tags'])}]" if entry["tags"] else ""
            lines.append(f"- {entry['content']}{tag_str}")
        return "\n".join(lines)
