from helpers import ev

from doma.state import HuntState, project


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


def test_dead_listing_reappearing_is_a_relist() -> None:
    state = project([
        _seen("2026-07-01T09:00:00+00:00", "gp-001"),
        ev("2026-07-03T09:00:00+00:00", "listing_delisted", listing_id="gp-001"),
        _seen("2026-07-20T09:00:00+00:00", "gp-001", price=3300),
    ])
    listing = state.listings["gp-001"]
    assert listing.status == "active"
    assert listing.relist_count == 1
    assert listing.price == 3300


def test_relist_is_not_novel_inventory() -> None:
    state = project([
        _seen("2026-07-01T09:00:00+00:00", "gp-001"),
        ev("2026-07-03T09:00:00+00:00", "listing_delisted", listing_id="gp-001"),
        _seen("2026-07-20T09:00:00+00:00", "gp-001"),
    ])
    # Novelty stays at first sighting; a relist must not reset saturation.
    assert state.last_novel_ts["greenpoint"] == "2026-07-01T09:00:00+00:00"


def test_fresh_listing_has_zero_relists() -> None:
    state = project([_seen("2026-07-01T09:00:00+00:00", "gp-001")])
    assert state.listings["gp-001"].relist_count == 0


def test_price_history_accumulates() -> None:
    state = project([
        _seen("2026-07-01T09:00:00+00:00", "gp-001", price=3000),
        ev("2026-07-05T09:00:00+00:00", "price_changed",
           listing_id="gp-001", price=2900),
        ev("2026-07-09T09:00:00+00:00", "price_changed",
           listing_id="gp-001", price=2800),
    ])
    assert state.listings["gp-001"].price_history == [
        ["2026-07-01T09:00:00+00:00", 3000],
        ["2026-07-05T09:00:00+00:00", 2900],
        ["2026-07-09T09:00:00+00:00", 2800],
    ]


def test_enrichment_and_attempted_fold() -> None:
    state = project([
        _seen("2026-07-01T09:00:00+00:00", "gp-001"),
        ev("2026-07-02T09:00:00+00:00", "enrichment_added",
           listing_id="gp-001", kind="hpd_violations",
           class_a=1, class_b=2, class_c=0, total=3),
        ev("2026-07-02T09:00:00+00:00", "enrichment_added",
           listing_id="gp-001", kind="commute",
           station="Nassau Av", walk_meters=393),
        ev("2026-07-02T09:00:00+00:00", "enrichment_attempted",
           listing_id="gp-001", ok=True),
    ])
    listing = state.listings["gp-001"]
    assert listing.hpd == {"class_a": 1, "class_b": 2, "class_c": 0, "total": 3}
    assert listing.commute == {"station": "Nassau Av", "walk_meters": 393}
    assert listing.enrich_attempted_ts == "2026-07-02T09:00:00+00:00"


def test_score_and_bait_fold() -> None:
    state = project([
        _seen("2026-07-01T09:00:00+00:00", "gp-001"),
        ev("2026-07-02T10:00:00+00:00", "score_computed",
           listing_id="gp-001", score=0.72, confidence=0.55,
           subscores={"rent_value": 0.8}),
        ev("2026-07-02T10:00:00+00:00", "bait_flagged",
           listing_id="gp-001", kind="relist", evidence={"relist_count": 1}),
    ])
    listing = state.listings["gp-001"]
    assert listing.score == 0.72
    assert listing.score_confidence == 0.55
    assert listing.score_ts == "2026-07-02T10:00:00+00:00"
    assert listing.bait_flags == ["relist"]


def test_listing_seen_carries_location_and_fee() -> None:
    state = project([ev("2026-07-01T09:00:00+00:00", "listing_seen",
                        listing_id="x", source="rentcast",
                        neighborhood="11222", price=3000,
                        address="55 Nassau Ave", unit=None, fee=None,
                        lat=40.7237, lon=-73.9509)])
    listing = state.listings["x"]
    assert listing.address == "55 Nassau Ave"
    assert listing.lat == 40.7237
    assert listing.fee is None


def test_listing_marked_sets_status() -> None:
    state = project([
        _seen("2026-07-01T09:00:00+00:00", "gp-001"),
        ev("2026-07-14T09:00:00+00:00", "listing_marked",
           listing_id="gp-001", status="rejected"),
    ])
    assert state.listings["gp-001"].status == "rejected"


def test_viewing_scored_folds_latest_scorecard() -> None:
    state = project([
        _seen("2026-07-01T09:00:00+00:00", "gp-001"),
        ev("2026-07-14T09:00:00+00:00", "viewing_scored",
           listing_id="gp-001", verdict="pass", ratings={"light": 2}),
    ])
    assert state.listings["gp-001"].scorecard == {"verdict": "pass",
                                                  "ratings": {"light": 2}}


def test_subscores_folded_from_score_event() -> None:
    state = project([
        _seen("2026-07-01T09:00:00+00:00", "gp-001"),
        ev("2026-07-02T10:00:00+00:00", "score_computed",
           listing_id="gp-001", score=0.7, confidence=0.5,
           subscores={"rent_value": 0.8, "light": None}),
    ])
    assert state.listings["gp-001"].subscores == {"rent_value": 0.8,
                                                  "light": None}


def test_novel_listing_desaturates_neighborhood() -> None:
    state = project([
        _seen("2026-07-01T09:00:00+00:00", "gp-001"),
        ev("2026-07-09T09:00:00+00:00", "neighborhood_saturated",
           neighborhood="greenpoint"),
        _seen("2026-07-20T09:00:00+00:00", "gp-002"),  # novel inventory
    ])
    assert "greenpoint" not in state.saturated


def test_source_history_seeds_prices_and_windowed_relists() -> None:
    state = project([ev("2026-07-13T09:00:00+00:00", "listing_seen",
                        listing_id="shell", source="rentcast",
                        neighborhood="11224", price=3450,
                        history=[["2026-06-09", 3300, True],
                                 ["2026-07-13", 3450, False]])])
    listing = state.listings["shell"]
    assert listing.relist_count == 1          # 33-day gap: bait
    assert listing.price_history[0] == ["2026-06-09", 3300]


def test_source_history_old_removal_is_not_a_relist() -> None:
    state = project([ev("2026-07-13T09:00:00+00:00", "listing_seen",
                        listing_id="x", source="rentcast",
                        neighborhood="11224", price=3950,
                        history=[["2025-06-09", 3850, True],
                                 ["2026-07-13", 3950, False]])])
    assert state.listings["x"].relist_count == 0  # 13-month gap: turnover


def test_outreach_folds() -> None:
    state = project([
        _seen("2026-07-01T09:00:00+00:00", "gp-001"),
        ev("2026-07-15T09:00:00+00:00", "outreach_proposed",
           listing_id="gp-001", draft="Hello!", generation_method="fallback"),
        ev("2026-07-15T10:00:00+00:00", "outreach_approved",
           listing_id="gp-001"),
    ])
    listing = state.listings["gp-001"]
    assert listing.outreach["draft"] == "Hello!"
    assert listing.outreach_status == "approved"


def test_listing_updated_backfills_photo() -> None:
    state = project([
        _seen("2026-07-01T09:00:00+00:00", "gp-001"),
        ev("2026-07-15T09:00:00+00:00", "listing_updated",
           listing_id="gp-001", price=3000,
           photo_url="https://photos.example/x.png"),
    ])
    assert state.listings["gp-001"].photo_url == "https://photos.example/x.png"
