"""Persistent local memory (fabric-lite) — SQLite + FTS5, on your machine only.

Every entry is stored locally in ``$TATTVA_HOME/memory.sqlite3`` (default
``~/.tattva``). Full-text search uses SQLite FTS5; no embeddings, no network.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path

from .nebius import tattva_home

_SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    id         INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    kind       TEXT NOT NULL DEFAULT 'note',
    source     TEXT NOT NULL DEFAULT 'human',
    text       TEXT NOT NULL,
    tags       TEXT NOT NULL DEFAULT '[]',
    sha256     TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
    text, tags, content='entries', content_rowid='id'
);
CREATE TRIGGER IF NOT EXISTS entries_ai AFTER INSERT ON entries BEGIN
    INSERT INTO entries_fts(rowid, text, tags) VALUES (new.id, new.text, new.tags);
END;
CREATE TRIGGER IF NOT EXISTS entries_ad AFTER DELETE ON entries BEGIN
    INSERT INTO entries_fts(entries_fts, rowid, text, tags)
    VALUES ('delete', old.id, old.text, old.tags);
END;
"""


def _fts_query(raw: str) -> str:
    """Turn arbitrary user text into a safe FTS5 MATCH query.

    Every whitespace-separated token becomes a quoted phrase, so FTS5
    operators (``-``, ``*``, ``NEAR``, column filters, …) are neutralised and
    treated as literal text; tokens are joined with implicit AND.
    """
    tokens = raw.split()
    return " ".join('"' + t.replace('"', '""') + '"' for t in tokens)


class Memory:
    """Local persistent memory. Entries never leave the machine."""

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path is not None else (tattva_home() / "memory.sqlite3")
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        try:
            self.conn.executescript(_SCHEMA)
        except sqlite3.OperationalError as exc:  # e.g. SQLite built without FTS5
            raise RuntimeError(
                f"SQLite FTS5 is required but unavailable here: {exc}"
            ) from exc
        self.conn.commit()

    # -- writes ------------------------------------------------------------
    def add(self, text: str, *, kind: str = "note", source: str = "human", tags: list[str] | None = None) -> int:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        cur = self.conn.execute(
            "INSERT INTO entries (created_at, kind, source, text, tags, sha256) VALUES (?, ?, ?, ?, ?, ?)",
            (
                time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                kind,
                source,
                text,
                json.dumps(tags or [], ensure_ascii=False),
                digest,
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    # -- reads -------------------------------------------------------------
    def search(self, query: str, *, limit: int = 5) -> list[dict]:
        match = _fts_query(query)
        if not match:
            return []
        rows = self.conn.execute(
            """
            SELECT e.id, e.created_at, e.kind, e.source, e.text, e.tags,
                   bm25(entries_fts) AS score
            FROM entries_fts f
            JOIN entries e ON e.id = f.rowid
            WHERE entries_fts MATCH ?
            ORDER BY score
            LIMIT ?
            """,
            (match, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def recent(self, *, limit: int = 10) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id, created_at, kind, source, text, tags FROM entries ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def count(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0])

    def close(self) -> None:
        self.conn.close()
