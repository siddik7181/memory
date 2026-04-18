from pathlib import Path

MEMORY_DIR = Path.home() / ".memory-load"
CHROMA_DIR = MEMORY_DIR / "chroma"
SESSIONS_DIR = Path.home() / ".claude" / "projects"
COLLECTION_NAME = "claude_memory"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 512  # chars per chunk
TOP_K = 5
