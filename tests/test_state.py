from helpers import ev

from hunt.state import HuntState, project


def _seen(ts: str, lid: str, hood: str = "greenpoint", price: int | None = 3000):
    return ev(ts, "listing_seen", listing_id=lid, source="rentcast",
              neighborhood=hood, price=price)


def test_listing_seen_creates_active_listing() -> None:
    state = project([_seen("2026-07-01T09:00:00+00:00", "gp-001")])
    listing = state.listings["gp-001"]
    assert listing.status == "active"
    assert listing.price == 3000
    assert listing.first_seen_ts == "2026-07-01T09:00:00+00:00"


def test_repeat_sighting_updates_last_seen_only() -> None:
    state = project([
        _seen("2026-07-01T09:00:00+00:00", "gp-001"),
        _seen("2026-07-02T09:00:00+00:00", "gp-001"),
    ])
    listing = state.listings["gp-001"]
    assert listing.first_seen_ts == "2026-07-01T09:00:00+00:00"
    assert listing.last_seen_ts == "2026-07-02T09:00:00+00:00"


def test_price_changed_updates_price() -> None:
    state = project([
        _seen("2026-07-01T09:00:00+00:00", "gp-001"),
        ev("2026-07-02T09:00:00+00:00", "price_changed",
           listing_id="gp-001", price=2800),
    ])
    assert state.listings["gp-001"].price == 2800


def test_delisted_marks_dead() -> None:
    state = project([
        _seen("2026-07-01T09:00:00+00:00", "gp-001"),
        ev("2026-07-03T09:00:00+00:00", "listing_delisted", listing_id="gp-001"),
    ])
    assert state.listings["gp-001"].status == "dead"


def test_price_none_stays_none() -> None:
    state = project([_seen("2026-07-01T09:00:00+00:00", "gp-001", price=None)])
    assert state.listings["gp-001"].price is None


def test_empty_projection() -> None:
    state = project([])
    assert state == HuntState(listings={}, last_scan_ts=None, scan_months={},
                              last_novel_ts={}, saturated=set())


def test_scan_bookkeeping() -> None:
    state = project([
        ev("2026-07-01T09:00:00+00:00", "budget_spent", resource="rentcast_scan"),
        ev("2026-07-01T09:00:00+00:00", "scan_completed", source="rentcast"),
        ev("2026-08-01T09:00:00+00:00", "budget_spent", resource="rentcast_scan"),
        ev("2026-08-01T09:00:00+00:00", "scan_completed", source="rentcast"),
    ])
    assert state.scan_months == {"2026-07": 1, "2026-08": 1}
    assert state.last_scan_ts == "2026-08-01T09:00:00+00:00"


def test_novelty_tracks_first_sightings_per_neighborhood() -> None:
    state = project([
        _seen("2026-07-01T09:00:00+00:00", "gp-001", hood="greenpoint"),
        _seen("2026-07-02T09:00:00+00:00", "gp-001", hood="greenpoint"),  # repeat
        _seen("2026-07-03T09:00:00+00:00", "wb-001", hood="williamsburg"),
    ])
    assert state.last_novel_ts == {
        "greenpoint": "2026-07-01T09:00:00+00:00",
        "williamsburg": "2026-07-03T09:00:00+00:00",
    }


def test_saturated_projection() -> None:
    state = project([
        ev("2026-07-10T09:00:00+00:00", "neighborhood_saturated",
           neighborhood="greenpoint"),
    ])
    assert state.saturated == {"greenpoint"}
