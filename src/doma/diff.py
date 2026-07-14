"""Pure differ: one source's scan snapshot vs projected state -> input events.

This is where live mode manufactures the same event stream that replay
corpora record. Delisting is scoped to the scanned source: a source can only
retract listings it reported itself.
"""
from __future__ import annotations

from typing import Any

from doma.events import Event
from doma.resolver import canonical_id
from doma.snapshot import Snapshot
from doma.state import HuntState


def _seen_payload(lid: str, snap: Snapshot) -> dict[str, Any]:
    return {
        "listing_id": lid, "source": snap.source, "source_id": snap.source_id,
        "address": snap.address_line1, "unit": snap.unit,
        "neighborhood": snap.neighborhood, "price": snap.price,
        "beds": snap.beds, "baths": snap.baths, "sqft": snap.sqft,
        "url": snap.url, "fee": snap.fee,
        "days_on_market": snap.days_on_market,
        "listed_date": snap.listed_date,
        "lat": snap.lat,
        "lon": snap.lon,
        "history": snap.history,
        "photo_url": snap.photo_url,
    }


def diff_scan(state: HuntState, snapshots: list[Snapshot], source: str,
              ts: str, full_snapshot: bool = True) -> list[Event]:
    """Compare one source's sighting against current state.

    full_snapshot=True (a scan) also delists this source's listings that
    are absent. Incremental sources (alert emails carry only NEW listings)
    pass False — absence there means nothing.
    """
    events: list[Event] = []
    seen_ids: set[str] = set()
    for snap in snapshots:
        lid = canonical_id(snap)
        seen_ids.add(lid)
        known = state.listings.get(lid)
        if known is None or known.status == "dead":
            # New listing — or a dead one returning (projection counts relist).
            events.append(Event(ts=ts, type="listing_seen",
                                payload=_seen_payload(lid, snap)))
        elif snap.price is not None and snap.price != known.price:
            events.append(Event(ts=ts, type="price_changed",
                                payload={"listing_id": lid,
                                         "price": snap.price}))
        else:
            events.append(Event(ts=ts, type="listing_updated",
                                payload={"listing_id": lid,
                                         "price": snap.price,
                                         "photo_url": snap.photo_url}))
    if not full_snapshot:
        return events
    for lid, listing in state.listings.items():
        if (listing.source == source and listing.status == "active"
                and lid not in seen_ids):
            events.append(Event(ts=ts, type="listing_delisted",
                                payload={"listing_id": lid}))
    return events
