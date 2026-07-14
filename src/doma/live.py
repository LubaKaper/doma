"""Live mode: the Executor that touches real APIs. Fetching and enrichment
are injected callables so every code path stays testable without a network."""
from __future__ import annotations

import dataclasses
import time
from typing import Any, Callable

from doma.actions import (saturation_event, scan_bookkeeping,
                          score_batch_events)
from doma.clock import Clock
from doma.diff import diff_scan
from doma.events import Event, iso
from doma.policy import Action
from doma.scorer import DEFAULT_WEIGHTS
from doma.snapshot import Snapshot
from doma.state import ListingState, project
from doma.store import EventStore

Enricher = Callable[[ListingState], dict[str, Any] | None]


class LiveExecutor:
    """Executes actions against the real world (or an injected fetcher)."""

    def __init__(self, store: EventStore, fetcher: Callable[[], list[Snapshot]],
                 clock: Clock, sleep_seconds: int = 300,
                 hpd_fetch: Enricher | None = None,
                 commute_fn: Enricher | None = None,
                 geo_fetch: Enricher | None = None) -> None:
        self._store = store
        self._fetcher = fetcher
        self._clock = clock
        self._sleep_seconds = sleep_seconds
        self._hpd_fetch = hpd_fetch
        self._commute_fn = commute_fn
        self._geo_fetch = geo_fetch

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
        if action.type == "enrich_batch":
            return self._enrich(action.targets or (), now_iso)
        if action.type == "score_batch":
            state = project(self._store.read_all())
            return score_batch_events(state, action.targets or (),
                                      state.weights, now_iso)
        if action.type == "sleep":
            time.sleep(self._sleep_seconds)
            return []
        raise ValueError(f"live executor got unknown action: {action.type}")

    def _enrich(self, targets: tuple[str, ...], now_iso: str) -> list[Event]:
        """Run each injected enricher per listing; failures are recorded,
        never silent, and never crash the loop."""
        state = project(self._store.read_all())
        events: list[Event] = []
        for lid in targets:
            listing = state.listings.get(lid)
            if listing is None:
                continue
            errors: list[str] = []
            if self._geo_fetch is not None and (listing.lat is None
                                                or listing.zip is None):
                try:
                    geo = self._geo_fetch(listing)
                except Exception as exc:  # recorded below — not silent
                    geo = None
                    errors.append(f"geo: {exc}")
                if geo is not None:
                    events.append(Event(ts=now_iso, type="enrichment_added",
                                        payload={"listing_id": lid,
                                                 "kind": "geo", **geo}))
                    # Downstream enrichers in this same pass see the geocode.
                    listing = dataclasses.replace(
                        listing,
                        zip=geo.get("zip", listing.zip),
                        lat=listing.lat or geo.get("lat"),
                        lon=listing.lon or geo.get("lon"))
            for kind, fn in (("hpd_violations", self._hpd_fetch),
                             ("commute", self._commute_fn)):
                if fn is None:
                    continue
                try:
                    detail = fn(listing)
                except Exception as exc:  # recorded below — not silent
                    errors.append(f"{kind}: {exc}")
                    continue
                if detail is not None:
                    events.append(Event(ts=now_iso, type="enrichment_added",
                                        payload={"listing_id": lid,
                                                 "kind": kind, **detail}))
            events.append(Event(ts=now_iso, type="enrichment_attempted",
                                payload={"listing_id": lid,
                                         "ok": not errors,
                                         "errors": errors}))
        return events
