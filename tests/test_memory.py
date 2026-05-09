"""Tests for the MemoryStore and MemoryManager."""

import os
import tempfile

import pytest

from memory.store import MemoryStore
from memory.manager import MemoryManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_store(tmp_path):
    """Return a MemoryStore backed by a temp file."""
    return MemoryStore(path=str(tmp_path / "memories.json"))


@pytest.fixture
def tmp_manager(tmp_path):
    """Return a MemoryManager backed by a temp file."""
    return MemoryManager(store_path=str(tmp_path / "memories.json"))


# ---------------------------------------------------------------------------
# MemoryStore tests
# ---------------------------------------------------------------------------


class TestMemoryStore:
    def test_add_returns_entry_with_id(self, tmp_store):
        entry = tmp_store.add("Hello, world!")
        assert "id" in entry
        assert entry["content"] == "Hello, world!"
        assert entry["tags"] == []
        assert "created_at" in entry

    def test_add_with_tags(self, tmp_store):
        entry = tmp_store.add("User likes Python.", tags=["python", "preferences"])
        assert entry["tags"] == ["python", "preferences"]

    def test_all_returns_all_entries(self, tmp_store):
        tmp_store.add("First memory.")
        tmp_store.add("Second memory.")
        memories = tmp_store.all()
        assert len(memories) == 2

    def test_get_existing_memory(self, tmp_store):
        entry = tmp_store.add("Something to recall.")
        fetched = tmp_store.get(entry["id"])
        assert fetched is not None
        assert fetched["id"] == entry["id"]

    def test_get_missing_memory_returns_none(self, tmp_store):
        assert tmp_store.get("nonexistent-id") is None

    def test_search_by_content(self, tmp_store):
        tmp_store.add("The cat sat on the mat.")
        tmp_store.add("The dog barked loudly.")
        results = tmp_store.search("cat")
        assert len(results) == 1
        assert "cat" in results[0]["content"]

    def test_search_by_tag(self, tmp_store):
        tmp_store.add("User prefers dark mode.", tags=["ui", "preferences"])
        tmp_store.add("User is located in Berlin.", tags=["location"])
        results = tmp_store.search("preferences")
        assert len(results) == 1

    def test_search_case_insensitive(self, tmp_store):
        tmp_store.add("Python is great.")
        results = tmp_store.search("PYTHON")
        assert len(results) == 1

    def test_search_no_match(self, tmp_store):
        tmp_store.add("Something unrelated.")
        results = tmp_store.search("xyz123")
        assert results == []

    def test_delete_existing_memory(self, tmp_store):
        entry = tmp_store.add("To be deleted.")
        assert tmp_store.delete(entry["id"]) is True
        assert tmp_store.get(entry["id"]) is None

    def test_delete_nonexistent_returns_false(self, tmp_store):
        assert tmp_store.delete("does-not-exist") is False

    def test_clear_removes_all(self, tmp_store):
        tmp_store.add("First.")
        tmp_store.add("Second.")
        tmp_store.add("Third.")
        count = tmp_store.clear()
        assert count == 3
        assert tmp_store.all() == []

    def test_clear_empty_store(self, tmp_store):
        assert tmp_store.clear() == 0

    def test_persistence_across_instances(self, tmp_path):
        path = str(tmp_path / "shared.json")
        store1 = MemoryStore(path=path)
        entry = store1.add("Persisted memory.")

        store2 = MemoryStore(path=path)
        assert store2.get(entry["id"]) is not None


# ---------------------------------------------------------------------------
# MemoryManager tests
# ---------------------------------------------------------------------------


class TestMemoryManager:
    def test_remember_and_recall(self, tmp_manager):
        tmp_manager.remember("Alice is the user's name.")
        results = tmp_manager.recall("Alice")
        assert len(results) == 1
        assert "Alice" in results[0]["content"]

    def test_remember_with_tags(self, tmp_manager):
        tmp_manager.remember("Dark mode is preferred.", tags=["ui"])
        results = tmp_manager.recall("ui")
        assert len(results) == 1

    def test_forget(self, tmp_manager):
        entry = tmp_manager.remember("Temporary fact.")
        assert tmp_manager.forget(entry["id"]) is True
        assert tmp_manager.recall("Temporary") == []

    def test_forget_nonexistent(self, tmp_manager):
        assert tmp_manager.forget("bad-id") is False

    def test_all_memories(self, tmp_manager):
        tmp_manager.remember("Fact one.")
        tmp_manager.remember("Fact two.")
        memories = tmp_manager.all_memories()
        assert len(memories) == 2

    def test_clear_all(self, tmp_manager):
        tmp_manager.remember("To remove.")
        count = tmp_manager.clear_all()
        assert count == 1
        assert tmp_manager.all_memories() == []

    def test_format_for_context_empty(self, tmp_manager):
        assert tmp_manager.format_for_context() == ""

    def test_format_for_context_with_memories(self, tmp_manager):
        tmp_manager.remember("User is Alice.", tags=["identity"])
        tmp_manager.remember("User prefers Python.")
        context = tmp_manager.format_for_context()
        assert context.startswith("[Memories]")
        assert "User is Alice." in context
        assert "[identity]" in context
        assert "User prefers Python." in context

    def test_default_store_path_created(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        mgr = MemoryManager()
        expected = os.path.join(str(tmp_path), ".claude_memory", "memories.json")
        assert os.path.exists(expected)
