from doma.diff import diff_scan
from doma.resolver import canonical_id
from doma.snapshot import Snapshot
from doma.state import project

TS = "2026-07-10T09:00:00+00:00"


def _snap(source_id: str = "rc-1", address: str = "1208 Clay Ave",
          unit: str | None = "4N", price: int | None = 2400) -> Snapshot:
    return Snapshot(source="rentcast", source_id=source_id,
                    address_line1=address, unit=unit, neighborhood="10456",
                    price=price, beds=2, baths=1.0, sqft=850, url=None,
                    fee=None, days_on_market=12, listed_date=None)


def test_new_listing_emits_listing_seen_with_canonical_id() -> None:
    events = diff_scan(project([]), [_snap()], source="rentcast", ts=TS)
    assert [e.type for e in events] == ["listing_seen"]
    payload = events[0].payload
    assert payload["listing_id"] == canonical_id(_snap())
    assert payload["source"] == "rentcast"
    assert payload["source_id"] == "rc-1"
    assert payload["price"] == 2400
    assert payload["fee"] is None  # unknown survives as None


def test_price_change_emits_price_changed() -> None:
    first = diff_scan(project([]), [_snap(price=2400)], "rentcast", TS)
    state = project(first)
    events = diff_scan(state, [_snap(price=2300)], "rentcast",
                       "2026-07-11T09:00:00+00:00")
    assert [e.type for e in events] == ["price_changed"]
    assert events[0].payload["price"] == 2300


def test_unchanged_listing_emits_listing_updated() -> None:
    first = diff_scan(project([]), [_snap()], "rentcast", TS)
    state = project(first)
    events = diff_scan(state, [_snap()], "rentcast",
                       "2026-07-11T09:00:00+00:00")
    assert [e.type for e in events] == ["listing_updated"]


def test_missing_listing_emits_delisted_for_same_source_only() -> None:
    first = diff_scan(project([]), [_snap()], "rentcast", TS)
    state = project(first)
    events = diff_scan(state, [], "rentcast", "2026-07-11T09:00:00+00:00")
    assert [e.type for e in events] == ["listing_delisted"]
    # A scan from a DIFFERENT source must not delist rentcast listings.
    events2 = diff_scan(state, [], "streeteasy_email",
                        "2026-07-11T09:00:00+00:00")
    assert events2 == []


def test_same_unit_from_two_sources_is_one_listing() -> None:
    rc = _snap()
    se = Snapshot(source="streeteasy_email", source_id="se-9",
                  address_line1="1208 CLAY AVENUE", unit="4n",
                  neighborhood="10456", price=2400, beds=2, baths=1.0,
                  sqft=None, url="https://streeteasy.com/x", fee=False,
                  days_on_market=None, listed_date=None)
    state = project(diff_scan(project([]), [rc], "rentcast", TS))
    events = diff_scan(state, [se], "streeteasy_email",
                       "2026-07-11T09:00:00+00:00")
    # Same canonical id -> a sighting, not a new listing.
    assert [e.type for e in events] == ["listing_updated"]
