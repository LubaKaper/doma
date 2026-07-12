"""Live mode: the Executor that touches real APIs. Fetching is injected so
every code path stays testable without a network."""
from __future__ import annotations

import time
from typing import Callable

from doma.actions import saturation_event, scan_bookkeeping
from doma.clock import Clock
from doma.diff import diff_scan
from doma.events import Event, iso
from doma.policy import Action
from doma.snapshot import Snapshot
from doma.state import project
from doma.store import EventStore


class LiveExecutor:
    """Executes actions against the real world (or an injected fetcher)."""

    def __init__(self, store: EventStore, fetcher: Callable[[], list[Snapshot]],
                 clock: Clock, sleep_seconds: int = 300) -> None:
        self._store = store
        self._fetcher = fetcher
        self._clock = clock
        self._sleep_seconds = sleep_seconds

    def execute(self, action: Action) -> list[Event]:
        """Produce the events one action yields, hitting real sources."""
        now_iso = iso(self._clock.now())
        if action.type == "scan_rentcast":
            snapshots = self._fetcher()
            state = project(self._store.read_all())
            return (diff_scan(state, snapshots, "rentcast", now_iso)
                    + scan_bookkeeping(now_iso))
        if action.type == "mark_saturated":
            return [saturation_event(action, now_iso)]
        if action.type == "sleep":
            time.sleep(self._sleep_seconds)
            return []
        raise ValueError(f"live executor got unknown action: {action.type}")
