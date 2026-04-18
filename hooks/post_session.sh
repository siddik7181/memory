#!/usr/bin/env bash
# Claude Code Stop hook — auto-index new sessions into memory-load
# Add to .claude/settings.json:
#   "hooks": { "Stop": [{ "matcher": "", "hooks": [{ "type": "command", "command": "/path/to/hooks/post_session.sh" }] }] }

MEMORY_LOAD_DIR="$(cd "$(dirname "$0")/.." && pwd)"

uv run --project "$MEMORY_LOAD_DIR" python "$MEMORY_LOAD_DIR/cli.py" index \
  >> "$HOME/.memory-load/index.log" 2>&1
