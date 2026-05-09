"""Command-line interface for Claude's local memory."""

import argparse
import json
import sys

from .manager import MemoryManager


def _print_entry(entry: dict) -> None:
    tags = f"  tags: {', '.join(entry['tags'])}" if entry["tags"] else ""
    print(f"[{entry['id']}] {entry['content']}{tags}")
    print(f"  created: {entry['created_at']}")


def cmd_add(args: argparse.Namespace, mgr: MemoryManager) -> int:
    tags = args.tag or []
    entry = mgr.remember(args.content, tags=tags)
    print(f"Memory saved: {entry['id']}")
    return 0


def cmd_list(args: argparse.Namespace, mgr: MemoryManager) -> int:
    memories = mgr.all_memories()
    if not memories:
        print("No memories stored.")
        return 0
    for entry in memories:
        _print_entry(entry)
    return 0


def cmd_search(args: argparse.Namespace, mgr: MemoryManager) -> int:
    results = mgr.recall(args.query)
    if not results:
        print(f"No memories found matching '{args.query}'.")
        return 0
    for entry in results:
        _print_entry(entry)
    return 0


def cmd_delete(args: argparse.Namespace, mgr: MemoryManager) -> int:
    if mgr.forget(args.id):
        print(f"Memory {args.id} deleted.")
        return 0
    print(f"Memory {args.id} not found.", file=sys.stderr)
    return 1


def cmd_clear(args: argparse.Namespace, mgr: MemoryManager) -> int:
    count = mgr.clear_all()
    print(f"Cleared {count} memory/memories.")
    return 0


def cmd_context(args: argparse.Namespace, mgr: MemoryManager) -> int:
    context = mgr.format_for_context()
    if context:
        print(context)
    else:
        print("No memories to include in context.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="claude-memory",
        description="Manage Claude's local memory.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # add
    p_add = sub.add_parser("add", help="Store a new memory.")
    p_add.add_argument("content", help="The text to remember.")
    p_add.add_argument(
        "--tag", "-t", action="append", metavar="TAG", help="Tag (repeatable)."
    )

    # list
    sub.add_parser("list", help="List all memories.")

    # search
    p_search = sub.add_parser("search", help="Search memories.")
    p_search.add_argument("query", help="Search query.")

    # delete
    p_delete = sub.add_parser("delete", help="Delete a memory by ID.")
    p_delete.add_argument("id", help="Memory ID.")

    # clear
    sub.add_parser("clear", help="Delete all memories.")

    # context
    sub.add_parser("context", help="Print memories formatted for a system prompt.")

    return parser


_COMMANDS = {
    "add": cmd_add,
    "list": cmd_list,
    "search": cmd_search,
    "delete": cmd_delete,
    "clear": cmd_clear,
    "context": cmd_context,
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    mgr = MemoryManager()
    return _COMMANDS[args.command](args, mgr)


if __name__ == "__main__":
    sys.exit(main())
