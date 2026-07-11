"""JSONL corpora of recorded input events, used by replay mode and fixtures."""
from __future__ import annotations

from pathlib import Path

from doma.events import INPUT_EVENT_TYPES, Event, from_json, to_json


def load_corpus(path: str | Path) -> list[Event]:
    """Load a JSONL corpus; only input events allowed; returns ts-sorted."""
    p = Path(path)
    try:
        lines = p.read_text().splitlines()
    except OSError as exc:
        raise RuntimeError(f"failed to read corpus {p}: {exc}") from exc
    events: list[Event] = []
    for lineno, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        event = from_json(line)
        if event.type not in INPUT_EVENT_TYPES:
            raise ValueError(
                f"{p}:{lineno}: {event.type} is not an input event type"
            )
        events.append(event)
    return sorted(events, key=lambda e: e.ts)


def save_corpus(events: list[Event], path: str | Path) -> None:
    """Write events as one JSON object per line."""
    Path(path).write_text("".join(to_json(e) + "\n" for e in events))
