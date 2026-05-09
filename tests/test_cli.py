"""Tests for the CLI interface."""

import pytest

from memory.cli import main
from memory.manager import MemoryManager


@pytest.fixture
def mgr(tmp_path):
    return MemoryManager(store_path=str(tmp_path / "memories.json"))


@pytest.fixture
def store_path(tmp_path):
    return str(tmp_path / "memories.json")


def _run(args, capsys, store_path):
    """Parse *args* and invoke the matching CLI command against a store at *store_path*."""
    from memory import MemoryManager
    from memory import cli as cli_module

    mgr = MemoryManager(store_path=store_path)
    parser = cli_module.build_parser()
    parsed = parser.parse_args(args)
    return cli_module._COMMANDS[parsed.command](parsed, mgr)


class TestCLI:
    def test_add_command(self, capsys, store_path):
        rc = _run(["add", "Remember this!"], capsys, store_path)
        assert rc == 0
        out = capsys.readouterr().out
        assert "Memory saved:" in out

    def test_add_with_tags(self, capsys, store_path):
        rc = _run(["add", "Tagged memory.", "--tag", "work", "--tag", "todo"], capsys, store_path)
        assert rc == 0

    def test_list_empty(self, capsys, store_path):
        rc = _run(["list"], capsys, store_path)
        assert rc == 0
        out = capsys.readouterr().out
        assert "No memories" in out

    def test_list_with_entries(self, capsys, store_path):
        _run(["add", "First entry."], capsys, store_path)
        _run(["add", "Second entry."], capsys, store_path)
        capsys.readouterr()  # flush
        rc = _run(["list"], capsys, store_path)
        assert rc == 0
        out = capsys.readouterr().out
        assert "First entry." in out
        assert "Second entry." in out

    def test_search_found(self, capsys, store_path):
        _run(["add", "Python is great."], capsys, store_path)
        capsys.readouterr()
        rc = _run(["search", "Python"], capsys, store_path)
        assert rc == 0
        out = capsys.readouterr().out
        assert "Python is great." in out

    def test_search_not_found(self, capsys, store_path):
        _run(["add", "Unrelated entry."], capsys, store_path)
        capsys.readouterr()
        rc = _run(["search", "xyz123"], capsys, store_path)
        assert rc == 0
        out = capsys.readouterr().out
        assert "No memories found" in out

    def test_delete_existing(self, capsys, store_path):
        _run(["add", "Will be deleted."], capsys, store_path)
        mgr = MemoryManager(store_path=store_path)
        memory_id = mgr.all_memories()[0]["id"]
        capsys.readouterr()
        rc = _run(["delete", memory_id], capsys, store_path)
        assert rc == 0
        out = capsys.readouterr().out
        assert "deleted" in out

    def test_delete_nonexistent(self, capsys, store_path):
        rc = _run(["delete", "bad-id"], capsys, store_path)
        assert rc == 1

    def test_clear(self, capsys, store_path):
        _run(["add", "One."], capsys, store_path)
        _run(["add", "Two."], capsys, store_path)
        capsys.readouterr()
        rc = _run(["clear"], capsys, store_path)
        assert rc == 0
        out = capsys.readouterr().out
        assert "2" in out

    def test_context_empty(self, capsys, store_path):
        rc = _run(["context"], capsys, store_path)
        assert rc == 0
        out = capsys.readouterr().out
        assert "No memories" in out

    def test_context_with_memories(self, capsys, store_path):
        _run(["add", "User is Alice.", "--tag", "identity"], capsys, store_path)
        capsys.readouterr()
        rc = _run(["context"], capsys, store_path)
        assert rc == 0
        out = capsys.readouterr().out
        assert "[Memories]" in out
        assert "User is Alice." in out
