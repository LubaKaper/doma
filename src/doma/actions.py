"""Events produced by internal actions — identical in live and replay mode."""
from __future__ import annotations

from doma.bait import detect
from doma.events import Event
from doma.policy import Action
from doma.scorer import score_listing
from doma.state import HuntState


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


def score_batch_events(state: HuntState, targets: tuple[str, ...],
                       weights: dict[str, float], now_iso: str) -> list[Event]:
    """Score + bait-check the targeted listings. Pure; shared by both modes.

    Emits score_computed even when nothing is knowable (score=None,
    confidence 0.0) so a listing is never re-queued forever.
    """
    events: list[Event] = []
    for lid in targets:
        listing = state.listings.get(lid)
        if listing is None:
            continue
        result = score_listing(listing, state, weights)
        if result is not None:
            events.append(Event(ts=now_iso, type="score_computed",
                                payload={"listing_id": lid,
                                         "score": result.score,
                                         "confidence": result.confidence,
                                         "subscores": result.subscores}))
        else:
            events.append(Event(ts=now_iso, type="score_computed",
                                payload={"listing_id": lid, "score": None,
                                         "confidence": 0.0,
                                         "subscores": {}}))
        for flag in detect(listing):
            if flag["kind"] not in listing.bait_flags:
                events.append(Event(ts=now_iso, type="bait_flagged",
                                    payload={"listing_id": lid,
                                             "kind": flag["kind"],
                                             "evidence": flag["evidence"]}))
    return events
