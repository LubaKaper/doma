"""Events produced by internal actions — identical in live and replay mode."""
from __future__ import annotations

from doma.events import Event
from doma.policy import Action


def scan_bookkeeping(now_iso: str) -> list[Event]:
    """Budget + completion events appended after every RentCast scan."""
    return [
        Event(ts=now_iso, type="budget_spent",
              payload={"resource": "rentcast_scan"}),
        Event(ts=now_iso, type="scan_completed",
              payload={"source": "rentcast"}),
    ]


def saturation_event(action: Action, now_iso: str) -> Event:
    """The neighborhood_saturated event for a mark_saturated action."""
    return Event(ts=now_iso, type="neighborhood_saturated",
                 payload={"neighborhood": action.target})
