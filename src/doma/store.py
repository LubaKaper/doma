"""Append-only SQLite event store. The only writer of persistent state."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from doma.events import Event

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    seq     INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      TEXT NOT NULL,
    type    TEXT NOT NULL,
    payload TEXT NOT NULL
)
"""


class EventStore:
    """Append-only event log backed by SQLite (file path or ':memory:')."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        try:
            self._conn = sqlite3.connect(str(path))
            # Dashboard and CLI share the file: WAL + a busy timeout turn
            # concurrent appends into short waits instead of hard errors.
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
            self._conn.execute(_SCHEMA)
            self._conn.commit()
        except sqlite3.Error as exc:
            raise RuntimeError(f"failed to open event store at {path}: {exc}") from exc

    def append(self, event: Event) -> Event:
        """Append one event; returns a copy with its assigned seq."""
        cur = self._conn.execute(
            "INSERT INTO events (ts, type, payload) VALUES (?, ?, ?)",
            (event.ts, event.type, json.dumps(event.payload, sort_keys=True)),
        )
        self._conn.commit()
        return Event(ts=event.ts, type=event.type,
                     payload=event.payload, seq=cur.lastrowid)

    def read_all(self) -> list[Event]:
        """Return every event in append (seq) order."""
        rows = self._conn.execute(
            "SELECT seq, ts, type, payload FROM events ORDER BY seq"
        ).fetchall()
        return [Event(ts=ts, type=type_, payload=json.loads(payload), seq=seq)
                for seq, ts, type_, payload in rows]
