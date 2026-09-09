"""Idempotent SQLite projection — rebuildable from events.jsonl + snapshots.

The DB is **derived, never canonical**. ``build_projection`` drops and recreates
all tables, so it is idempotent and can be re-run after deleting the file.

Usage:
    from fused.projection import build_projection
    build_projection("knowledge/fused-demo/events.jsonl", "knowledge/fused-demo/projections/campaign.db")

Cheap queries (no LLM):
    sqlite3 projections/campaign.db "SELECT actor, count(*) FROM events GROUP BY actor"
    sqlite3 projections/campaign.db "SELECT * FROM wounds WHERE actor='Elaria'"
"""

from __future__ import annotations

import json
import pathlib as _pl
import sqlite3

from .events import iter_events

SCHEMA_SQL = """
DROP TABLE IF EXISTS events;
DROP VIEW IF EXISTS wounds;

CREATE TABLE events(
    seq INTEGER PRIMARY KEY,
    id TEXT UNIQUE NOT NULL,
    time TEXT NOT NULL,
    type TEXT NOT NULL,
    source TEXT NOT NULL,
    subject TEXT NOT NULL,
    scene_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    round INTEGER NOT NULL,
    summary TEXT NOT NULL,
    payload TEXT NOT NULL,  -- JSON
    snapshot_ref TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_scene ON events(scene_id);
CREATE INDEX IF NOT EXISTS idx_events_actor ON events(subject);
CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);

CREATE VIEW wounds AS
  SELECT seq, id, time, subject AS actor, scene_id, round, summary,
         json_extract(payload, '$.wound') AS wound,
         json_extract(payload, '$.damage') AS damage,
         payload
  FROM events
  WHERE json_extract(payload, '$.wound') IS NOT NULL;
"""


def build_projection(
    events_path: str | _pl.Path,
    db_path: str | _pl.Path,
    *,
    overwrite: bool = True,
) -> _pl.Path:
    """(Re)build SQLite projection from ``events.jsonl``. Idempotent.

    If ``db_path`` exists and ``overwrite`` is True, schema is dropped/recreated.
    If ``overwrite`` is False and the DB already exists, it is left untouched.
    Returns path to DB. Raises if event validation fails.
    """
    ep = _pl.Path(events_path)
    db = _pl.Path(db_path)
    db.parent.mkdir(parents=True, exist_ok=True)
    if not overwrite and db.exists():
        return db

    # Remove existing DB atomically for overwrite idempotence if requested
    # Instead of deleting file, we open and DDL-drop so an existing handle sees new data.
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(SCHEMA_SQL)
        # Bulk insert from log
        rows: list[tuple] = []
        for seq, evt in enumerate(iter_events(ep)):
            fused = evt.get("fused", {})
            data = evt.get("data", {})
            payload = data.get("payload", {})
            rows.append(
                (
                    seq,
                    evt.get("id"),
                    evt.get("time"),
                    evt.get("type"),
                    evt.get("source"),
                    evt.get("subject"),
                    fused.get("scene_id", ""),
                    fused.get("kind", ""),
                    int(fused.get("round", 0)),
                    data.get("summary", ""),
                    json.dumps(payload, separators=(",", ":"), default=str),
                    evt.get("snapshot_ref"),
                )
            )
        if rows:
            conn.executemany(
                "INSERT OR REPLACE INTO events(seq,id,time,type,source,subject,scene_id,kind,round,summary,payload,snapshot_ref) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                rows,
            )
        conn.commit()
    finally:
        conn.close()
    return db


def query_wounds(db_path: str | _pl.Path, actor: str | None = None) -> list[dict]:
    db = _pl.Path(db_path)
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        if actor:
            cur = conn.execute("SELECT * FROM wounds WHERE actor = ?", (actor,))
        else:
            cur = conn.execute("SELECT * FROM wounds")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def query_events(
    db_path: str | _pl.Path,
    *,
    actor: str | None = None,
    scene_id: str | None = None,
    kind: str | None = None,
    last_n: int | None = None,
) -> list[dict]:
    db = _pl.Path(db_path)
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        clauses: list[str] = []
        params: list[object] = []
        if actor:
            clauses.append("subject = ?")
            params.append(actor)
        if scene_id:
            clauses.append("scene_id = ?")
            params.append(scene_id)
        if kind:
            clauses.append("kind = ?")
            params.append(kind)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        order = "ORDER BY seq DESC" if last_n else "ORDER BY seq"
        limit = f"LIMIT {int(last_n)}" if last_n else ""
        sql = f"SELECT * FROM events {where} {order} {limit}"
        cur = conn.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]
        # if last_n, rows are desc — reverse to chronological
        if last_n:
            rows.reverse()
        return rows
    finally:
        conn.close()
