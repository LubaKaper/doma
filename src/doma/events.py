"""Event model: the single unit of truth in the doma event store."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

# Input events: recorded in replay corpora; produced by adapters in live mode.
INPUT_EVENT_TYPES = frozenset({
    "listing_seen", "listing_updated", "price_changed", "listing_delisted",
    "alert_email_received", "enrichment_added", "facts_extracted",
    "viewing_scored",
})

# Decision events: produced by the loop itself; recomputed during replay.
DECISION_EVENT_TYPES = frozenset({
    "scan_completed", "budget_spent", "score_computed", "bait_flagged",
    "outreach_proposed", "outreach_approved", "outreach_rejected",
    "viewing_scheduled", "weights_proposed", "weights_updated",
    "enrichment_attempted",
    "neighborhood_saturated",
})

EVENT_TYPES = INPUT_EVENT_TYPES | DECISION_EVENT_TYPES


@dataclass(frozen=True)
class Event:
    """One immutable fact. `seq` is None until the store assigns it."""

    ts: str  # ISO 8601 with UTC offset, e.g. "2026-07-01T09:00:00+00:00"
    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    seq: int | None = None

    def __post_init__(self) -> None:
        if self.type not in EVENT_TYPES:
            raise ValueError(f"unknown event type: {self.type}")


def iso(dt: datetime) -> str:
    """Format a timezone-aware datetime as a UTC ISO 8601 string."""
    if dt.tzinfo is None:
        raise ValueError("iso() requires a timezone-aware datetime")
    return dt.astimezone(timezone.utc).isoformat()


def parse_ts(ts: str) -> datetime:
    """Parse an ISO 8601 timestamp string into a timezone-aware datetime."""
    return datetime.fromisoformat(ts)


def to_json(event: Event) -> str:
    """Serialize an Event to a single JSON line."""
    return json.dumps(
        {"ts": event.ts, "type": event.type,
         "payload": event.payload, "seq": event.seq},
        sort_keys=True,
    )


def from_json(line: str) -> Event:
    """Deserialize a JSON line into an Event."""
    d = json.loads(line)
    return Event(ts=d["ts"], type=d["type"],
                 payload=d["payload"], seq=d.get("seq"))
