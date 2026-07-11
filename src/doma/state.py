"""HuntState: a pure projection of the event log. Never mutated elsewhere."""
from __future__ import annotations

from dataclasses import dataclass, field

from doma.events import Event

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


@dataclass
class HuntState:
    """Everything the policy engine needs, derived from events only."""

    listings: dict[str, ListingState] = field(default_factory=dict)
    last_scan_ts: str | None = None
    scan_months: dict[str, int] = field(default_factory=dict)  # "2026-07" -> n
    last_novel_ts: dict[str, str] = field(default_factory=dict)  # hood -> ts
    saturated: set[str] = field(default_factory=set)


def project(events: list[Event]) -> HuntState:
    """Fold the event list into a HuntState. Pure: same events, same state."""
    state = HuntState()
    for e in events:
        p = e.payload
        if e.type == "listing_seen":
            lid = p["listing_id"]
            existing = state.listings.get(lid)
            if existing is None:
                state.listings[lid] = ListingState(
                    listing_id=lid,
                    source=p["source"],
                    neighborhood=p["neighborhood"],
                    price=p.get("price"),
                    status="active",
                    first_seen_ts=e.ts,
                    last_seen_ts=e.ts,
                )
                state.last_novel_ts[p["neighborhood"]] = e.ts
            else:
                existing.last_seen_ts = e.ts
        elif e.type == "listing_updated":
            listing = state.listings.get(p["listing_id"])
            if listing is not None:
                listing.last_seen_ts = e.ts
                if p.get("price") is not None:
                    listing.price = p["price"]
        elif e.type == "price_changed":
            listing = state.listings.get(p["listing_id"])
            if listing is not None:
                listing.price = p["price"]
                listing.last_seen_ts = e.ts
        elif e.type == "listing_delisted":
            listing = state.listings.get(p["listing_id"])
            if listing is not None:
                listing.status = "dead"
        elif e.type == "scan_completed":
            state.last_scan_ts = e.ts
        elif e.type == "budget_spent" and p.get("resource") == "rentcast_scan":
            month = e.ts[:7]
            state.scan_months[month] = state.scan_months.get(month, 0) + 1
        elif e.type == "neighborhood_saturated":
            state.saturated.add(p["neighborhood"])
    return state
