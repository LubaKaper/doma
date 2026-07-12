"""Replay mode: recorded inputs in, recomputed decisions out."""
from __future__ import annotations

from datetime import datetime

from doma.actions import saturation_event, scan_bookkeeping
from doma.clock import ReplayClock
from doma.events import INPUT_EVENT_TYPES, Event, iso
from doma.loop import run_tick
from doma.policy import Action, PolicyConfig
from doma.store import EventStore

# Input events a RentCast scan would surface in live mode.
SCAN_DELIVERED = frozenset({
    "listing_seen", "listing_updated", "price_changed", "listing_delisted",
})
# Input events that arrive on their own (e.g. alert emails), delivered on sleep.
PUSH_DELIVERED = INPUT_EVENT_TYPES - SCAN_DELIVERED


class ReplayExecutor:
    """Serves recorded input events in response to the loop's actions."""

    def __init__(self, corpus: list[Event], clock: ReplayClock) -> None:
        self._pending = sorted(corpus, key=lambda e: e.ts)
        self._clock = clock

    def exhausted(self) -> bool:
        """True once every corpus event has been delivered."""
        return not self._pending

    def _take_due(self, types: frozenset[str], now_iso: str) -> list[Event]:
        due = [e for e in self._pending
               if e.ts <= now_iso and e.type in types]
        delivered = set(id(e) for e in due)
        self._pending = [e for e in self._pending if id(e) not in delivered]
        return due

    def execute(self, action: Action) -> list[Event]:
        """Produce the events this action yields at the current sim time."""
        now_iso = iso(self._clock.now())
        if action.type == "scan_rentcast":
            due = self._take_due(SCAN_DELIVERED, now_iso)
            return due + scan_bookkeeping(now_iso)
        if action.type == "mark_saturated":
            return [saturation_event(action, now_iso)]
        if action.type == "sleep":
            self._clock.advance()
            return self._take_due(PUSH_DELIVERED, iso(self._clock.now()))
        raise ValueError(f"replay executor got unknown action: {action.type}")


def run_replay(store: EventStore, config: PolicyConfig, corpus: list[Event],
               clock: ReplayClock, until: datetime,
               max_ticks: int = 1000) -> list[Action]:
    """Drive the loop over a corpus until sim time passes `until`.

    Returns the full action log. Raises if max_ticks is hit (livelock guard).
    """
    executor = ReplayExecutor(corpus, clock)
    actions: list[Action] = []
    for _ in range(max_ticks):
        if clock.now() > until:
            return actions
        action, _ = run_tick(store, config, executor, clock)
        actions.append(action)
    raise RuntimeError(f"replay did not reach {until} within {max_ticks} ticks")
