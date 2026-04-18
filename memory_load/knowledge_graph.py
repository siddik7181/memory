"""Temporal knowledge graph backed by SQLite.

Entities and relationships with optional validity windows.
"""

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime

from .config import MEMORY_DIR

KG_PATH = MEMORY_DIR / "kg.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS entities (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT NOT NULL,
    type    TEXT NOT NULL DEFAULT 'concept',
    created TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS relations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id  INTEGER NOT NULL REFERENCES entities(id),
    predicate   TEXT NOT NULL,
    object_id   INTEGER NOT NULL REFERENCES entities(id),
    valid_from  TEXT,
    valid_until TEXT,
    note        TEXT,
    created     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_relations_subject ON relations(subject_id);
CREATE INDEX IF NOT EXISTS idx_relations_object  ON relations(object_id);
"""


@contextmanager
def _conn():
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(KG_PATH)
    con.row_factory = sqlite3.Row
    try:
        con.executescript(SCHEMA)
        yield con
        con.commit()
    finally:
        con.close()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def add_entity(name: str, entity_type: str = "concept") -> int:
    """Add or return existing entity. Returns entity id."""
    with _conn() as con:
        row = con.execute(
            "SELECT id FROM entities WHERE name = ? AND type = ?", (name, entity_type)
        ).fetchone()
        if row:
            return row["id"]
        cur = con.execute(
            "INSERT INTO entities (name, type, created) VALUES (?, ?, ?)",
            (name, entity_type, _now()),
        )
        return cur.lastrowid


def add_relation(
    subject: str,
    predicate: str,
    obj: str,
    subject_type: str = "concept",
    object_type: str = "concept",
    valid_from: str | None = None,
    valid_until: str | None = None,
    note: str | None = None,
) -> int:
    """Add a relation between two entities. Returns relation id."""
    sid = add_entity(subject, subject_type)
    oid = add_entity(obj, object_type)
    with _conn() as con:
        cur = con.execute(
            """INSERT INTO relations
               (subject_id, predicate, object_id, valid_from, valid_until, note, created)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (sid, predicate, oid, valid_from, valid_until, note, _now()),
        )
        return cur.lastrowid


def invalidate_relation(relation_id: int) -> None:
    """Mark a relation as no longer valid (sets valid_until = now)."""
    with _conn() as con:
        con.execute(
            "UPDATE relations SET valid_until = ? WHERE id = ?",
            (_now(), relation_id),
        )


def query_entity(name: str, at: str | None = None) -> list[dict]:
    """Return all relations for an entity, optionally at a point in time."""
    ts = at or _now()
    with _conn() as con:
        rows = con.execute(
            """
            SELECT r.id, es.name as subject, r.predicate, eo.name as object,
                   r.valid_from, r.valid_until, r.note, r.created
            FROM relations r
            JOIN entities es ON r.subject_id = es.id
            JOIN entities eo ON r.object_id  = eo.id
            WHERE (es.name = ? OR eo.name = ?)
              AND (r.valid_from  IS NULL OR r.valid_from  <= ?)
              AND (r.valid_until IS NULL OR r.valid_until  > ?)
            ORDER BY r.created
            """,
            (name, name, ts, ts),
        ).fetchall()
        return [dict(r) for r in rows]


def list_entities(entity_type: str | None = None) -> list[dict]:
    with _conn() as con:
        if entity_type:
            rows = con.execute(
                "SELECT * FROM entities WHERE type = ? ORDER BY name", (entity_type,)
            ).fetchall()
        else:
            rows = con.execute("SELECT * FROM entities ORDER BY name").fetchall()
        return [dict(r) for r in rows]


def kg_stats() -> dict:
    with _conn() as con:
        entities = con.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
        relations = con.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
        active = con.execute("SELECT COUNT(*) FROM relations WHERE valid_until IS NULL").fetchone()[
            0
        ]
        return {"entities": entities, "relations": relations, "active_relations": active}
