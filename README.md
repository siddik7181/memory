# memory-load

Local-first semantic memory for AI CLIs. Index your conversation history, search by meaning, and expose everything via MCP to Claude Code, Codex CLI, Gemini CLI, and GitHub Copilot.

---

## What it does

- **Indexes** Claude Code session history (`~/.claude/projects/`) into a local vector database
- **Searches** by meaning, not keywords — ask "how did we fix that auth bug?" and get the right turn
- **Saves** manual memories with tags
- **Knowledge graph** — store entity relationships with temporal validity
- **MCP server** — all features available as tools in any MCP-compatible AI CLI

Everything stays on your machine. No API key required.

---

## Install

**Requirements:** Python 3.12+, [uv](https://docs.astral.sh/uv/)

```bash
git clone <repo-url> memory-load
cd memory-load
uv sync
```

---

## Quick start

```bash
# 1. Initialize storage
uv run python cli.py init

# 2. Index all your Claude Code sessions
uv run python cli.py index

# 3. Search
uv run python cli.py query "how did we set up the docker compose"

# 4. Stats
uv run python cli.py stat
```

---

## CLI reference

### Memory

| Command | Description |
|---------|-------------|
| `init` | Create `~/.memory-load/` directories |
| `index [-v]` | Index all `~/.claude/projects/` sessions |
| `query <text> [-k N] [-p project] [--since ISO8601]` | Semantic search |
| `save <text> [--tags a,b]` | Manually save a memory |
| `stat` | Show chunk count and indexed projects |
| `projects` | List all indexed project names |

```bash
# Filter by project name (use value from `projects` command)
uv run python cli.py query "redis caching" -p -Users-abu-siddik-myapp

# Filter by date
uv run python cli.py query "docker setup" --since 2026-01-01T00:00:00.000Z

# Top 10 results
uv run python cli.py query "auth flow" -k 10
```

### Knowledge graph

```bash
# Add a relation
uv run python cli.py kg add "myapp" "uses" "PostgreSQL" --note "primary DB"
uv run python cli.py kg add "myapp" "deployed_on" "Railway"

# Query an entity
uv run python cli.py kg query "myapp"
# [1] myapp --[uses]--> PostgreSQL
# [2] myapp --[deployed_on]--> Railway

# Expire a relation (when it's no longer true)
uv run python cli.py kg invalidate 1

# List all entities
uv run python cli.py kg entities

# Stats
uv run python cli.py kg stat
```

### MCP server

```bash
# stdio (for Claude Code, Codex CLI, Gemini CLI)
uv run python cli.py serve

# HTTP (for VS Code Copilot and HTTP MCP clients)
uv run python cli.py serve --transport http --host 127.0.0.1 --port 8765

# Streamable HTTP (modern clients)
uv run python cli.py serve --transport streamable-http --port 8765
```

---

## MCP integration by tool

### Claude Code

MCP servers go in `~/.mcp.json` (global) or `.mcp.json` in the project root:

```json
{
  "mcpServers": {
    "memory-load": {
      "command": "uv",
      "args": [
        "run",
        "--project", "/absolute/path/to/memory-load",
        "python", "cli.py", "serve"
      ]
    }
  }
}
```

The Stop hook goes in `~/.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "/absolute/path/to/memory-load/hooks/post_session.sh",
            "async": true
          }
        ]
      }
    ]
  }
}
```

Restart Claude Code. Tools available in every session:
`memory_search`, `memory_save`, `memory_index`, `memory_stats`, `memory_list_projects`,
`kg_add_relation`, `kg_query`, `kg_invalidate`, `kg_list_entities`, `kg_stats_tool`

### Codex CLI (OpenAI)

Add to `~/.codex/config.toml`:

```toml
[[mcp_servers]]
name = "memory-load"
command = "uv"
args = ["run", "--project", "/absolute/path/to/memory-load", "python", "cli.py", "serve"]
```

Or HTTP mode — start server first, then:

```toml
[[mcp_servers]]
name = "memory-load"
url = "http://127.0.0.1:8765/mcp"
```

### Gemini CLI

Add to `~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "memory-load": {
      "command": "uv",
      "args": [
        "run",
        "--project", "/absolute/path/to/memory-load",
        "python", "cli.py", "serve"
      ]
    }
  }
}
```

### GitHub Copilot (VS Code)

Start HTTP server:

```bash
uv run python cli.py serve --transport streamable-http --host 127.0.0.1 --port 8765
```

Add to VS Code `settings.json`:

```json
{
  "github.copilot.chat.mcp.servers": {
    "memory-load": {
      "url": "http://127.0.0.1:8765/mcp"
    }
  }
}
```

---

## Auto-index on session end (Claude Code hook)

Keeps memory current by re-indexing whenever a Claude Code session stops.

Add to `~/.claude/settings.json` (global, not project `settings.json`):

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "/absolute/path/to/memory-load/hooks/post_session.sh",
            "async": true
          }
        ]
      }
    ]
  }
}
```

`async: true` — runs in background, doesn't block Claude Code exit.  
Logs to `~/.memory-load/index.log`.

---

## Storage layout

```
~/.memory-load/
├── chroma/          # ChromaDB vector store (embeddings + documents)
├── kg.db            # SQLite knowledge graph
└── index.log        # Hook auto-index log
```

---

## MCP tools reference

| Tool | Args | Description |
|------|------|-------------|
| `memory_search` | `query, top_k=5, project="", since=""` | Semantic search |
| `memory_save` | `text, tags=""` | Save a memory manually |
| `memory_index` | — | Re-index all sessions |
| `memory_stats` | — | Chunk count + projects |
| `memory_list_projects` | — | List indexed project names |
| `kg_add_relation` | `subject, predicate, object, subject_type, object_type, note` | Add entity relation |
| `kg_query` | `entity, at=""` | Query relations (optionally at a point in time) |
| `kg_invalidate` | `relation_id` | Expire a relation |
| `kg_list_entities` | `entity_type=""` | List known entities |
| `kg_stats_tool` | — | Knowledge graph stats |

---

## Architecture

```
cli.py                       CLI entry point
memory_load/
├── config.py                paths, model, defaults
├── indexer.py               JSONL → chunk → embed → ChromaDB
├── search.py                embed query → ChromaDB top-k + filters
├── mcp_server.py            FastMCP server (10 tools)
└── knowledge_graph.py       SQLite entity-relation graph with validity windows
hooks/
└── post_session.sh          Claude Code Stop hook (auto-index)
```

**Embedding model:** `sentence-transformers/all-MiniLM-L6-v2` — local, ~90 MB, no API key  
**Vector store:** ChromaDB — persistent, local  
**Knowledge graph:** SQLite with temporal validity windows
