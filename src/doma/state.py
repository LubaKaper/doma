"""HuntState: a pure projection of the event log. Never mutated elsewhere."""
from __future__ import annotations

from datetime import date

from dataclasses import dataclass, field
from typing import Any

from doma.events import Event
from doma.weights import DEFAULT_WEIGHTS

# A prior removal only counts as a relist if the gap to the next listing
# is short — long gaps are normal turnover, not bait.
RELIST_WINDOW_DAYS = 90

# Listings in these statuses cost zero future actions (spec §4).
TERMINAL_STATUSES = frozenset({"rejected", "dead", "viewed", "pursuing"})


@dataclass
class ListingState:
    """Current view of one listing, folded from its events."""

    listing_id: str
    source: str
    neighborhood: str
    price: int | None
    status: str  # "active" or a TERMINAL_STATUSES member
    first_seen_ts: str
    last_seen_ts: str
    relist_count: int = 0
    # Location + facts carried on listing_seen (None when the source lacks them)
    address: str | None = None
    unit: str | None = None
    fee: bool | None = None
    lat: float | None = None
    lon: float | None = None
    # Accumulated history and enrichment
    price_history: list[list[Any]] = field(default_factory=list)  # [ts, price]
    hpd: dict[str, Any] | None = None
    commute: dict[str, Any] | None = None
    enrich_attempted_ts: str | None = None
    # Scoring
    score: float | None = None
    score_confidence: float | None = None
    score_ts: str | None = None
    subscores: dict[str, Any] = field(default_factory=dict)
    bait_flags: list[str] = field(default_factory=list)
    scorecard: dict[str, Any] | None = None


@dataclass
class HuntState:
    """Everything the policy engine needs, derived from events only."""

    listings: dict[str, ListingState] = field(default_factory=dict)
    last_scan_ts: str | None = None
    scan_months: dict[str, int] = field(default_factory=dict)  # "2026-07" -> n
    last_novel_ts: dict[str, str] = field(default_factory=dict)  # hood -> ts
    saturated: set[str] = field(default_factory=set)
    weights: dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_WEIGHTS))
    weights_ts: str | None = None


def _days_between(d1: str, d2: str) -> int:
    return abs((date.fromisoformat(d2[:10]) - date.fromisoformat(d1[:10])).days)


def _seed_source_history(listing: ListingState,
                         history: list[list]) -> None:
    """Fold the source's own prior sightings: prices always; a removal
    counts as a relist only when relisting followed within the window."""
    for i, entry in enumerate(history):
        entry_date, price, removed = entry[0], entry[1], entry[2]
        _record_price(listing, entry_date, price)
        if removed and i + 1 < len(history):
            next_date = history[i + 1][0]
            if _days_between(entry_date, next_date) <= RELIST_WINDOW_DAYS:
                listing.relist_count += 1


def _record_price(listing: ListingState, ts: str, price: int | None) -> None:
    if price is None:
        return
    if listing.price_history and listing.price_history[-1][1] == price:
        return
    listing.price_history.append([ts, price])


def project(events: list[Event]) -> HuntState:
    """Fold the event list into a HuntState. Pure: same events, same state."""
    state = HuntState()
    for e in events:
        p = e.payload
        if e.type == "listing_seen":
            lid = p["listing_id"]
            existing = state.listings.get(lid)
            if existing is None:
                listing = ListingState(
                    listing_id=lid,
                    source=p["source"],
                    neighborhood=p["neighborhood"],
                    price=p.get("price"),
                    status="active",
                    first_seen_ts=e.ts,
                    last_seen_ts=e.ts,
                    address=p.get("address"),
                    unit=p.get("unit"),
                    fee=p.get("fee"),
                    lat=p.get("lat"),
                    lon=p.get("lon"),
                )
                _seed_source_history(listing, p.get("history") or [])
                _record_price(listing, e.ts, p.get("price"))
                state.listings[lid] = listing
                state.last_novel_ts[p["neighborhood"]] = e.ts
                state.saturated.discard(p["neighborhood"])
            else:
                existing.last_seen_ts = e.ts
                if existing.status == "dead":
                    existing.status = "active"
                    existing.relist_count += 1
                if p.get("price") is not None:
                    existing.price = p["price"]
                    _record_price(existing, e.ts, p["price"])
        elif e.type == "listing_updated":
            listing = state.listings.get(p["listing_id"])
            if listing is not None:
                listing.last_seen_ts = e.ts
                if p.get("price") is not None:
                    listing.price = p["price"]
                    _record_price(listing, e.ts, p["price"])
        elif e.type == "price_changed":
            listing = state.listings.get(p["listing_id"])
            if listing is not None:
                listing.price = p["price"]
                listing.last_seen_ts = e.ts
                _record_price(listing, e.ts, p["price"])
        elif e.type == "listing_delisted":
            listing = state.listings.get(p["listing_id"])
            if listing is not None:
                listing.status = "dead"
        elif e.type == "enrichment_added":
            listing = state.listings.get(p.get("listing_id", ""))
            if listing is not None:
                detail = {k: v for k, v in p.items()
                          if k not in ("listing_id", "kind")}
                if p.get("kind") == "hpd_violations":
                    listing.hpd = detail
                elif p.get("kind") == "commute":
                    listing.commute = detail
        elif e.type == "enrichment_attempted":
            listing = state.listings.get(p.get("listing_id", ""))
            if listing is not None:
                listing.enrich_attempted_ts = e.ts
        elif e.type == "score_computed":
            listing = state.listings.get(p.get("listing_id", ""))
            if listing is not None:
                listing.score = p.get("score")
                listing.score_confidence = p.get("confidence")
                listing.score_ts = e.ts
                listing.subscores = p.get("subscores", {})
        elif e.type == "listing_marked":
            listing = state.listings.get(p.get("listing_id", ""))
            if listing is not None and p.get("status") in (
                    TERMINAL_STATUSES | {"active"}):
                listing.status = p["status"]
        elif e.type == "viewing_scored":
            listing = state.listings.get(p.get("listing_id", ""))
            if listing is not None:
                listing.scorecard = {"verdict": p.get("verdict"),
                                     "ratings": p.get("ratings", {})}
        elif e.type == "bait_flagged":
            listing = state.listings.get(p.get("listing_id", ""))
            if listing is not None and p.get("kind") not in listing.bait_flags:
                listing.bait_flags.append(p["kind"])
        elif e.type == "scan_completed":
            state.last_scan_ts = e.ts
        elif e.type == "budget_spent" and p.get("resource") == "rentcast_scan":
            month = e.ts[:7]
            state.scan_months[month] = state.scan_months.get(month, 0) + 1
        elif e.type == "weights_updated":
            if p.get("weights"):
                state.weights = dict(p["weights"])
                state.weights_ts = e.ts
        elif e.type == "neighborhood_saturated":
            state.saturated.add(p["neighborhood"])
    return state
