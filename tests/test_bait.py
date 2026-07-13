from doma.bait import detect
from doma.state import ListingState


def _listing(**kw) -> ListingState:
    base = dict(listing_id="x", source="rentcast", neighborhood="11222",
                price=3000, status="active",
                first_seen_ts="2026-07-01T09:00:00+00:00",
                last_seen_ts="2026-07-01T09:00:00+00:00")
    base.update(kw)
    return ListingState(**base)


def test_clean_listing_has_no_flags() -> None:
    assert detect(_listing()) == []


def test_relist_flagged_with_evidence() -> None:
    flags = detect(_listing(relist_count=2,
                            price_history=[["t1", 3300], ["t2", 3450]]))
    assert len(flags) == 1
    assert flags[0]["kind"] == "relist"
    assert flags[0]["evidence"]["relist_count"] == 2
    assert flags[0]["evidence"]["price_history"] == [["t1", 3300], ["t2", 3450]]


def test_price_laddering_needs_two_consecutive_drops() -> None:
    one_drop = _listing(price_history=[["t1", 3000], ["t2", 2900]])
    assert detect(one_drop) == []
    two_drops = _listing(price_history=[["t1", 3000], ["t2", 2900], ["t3", 2800]])
    flags = detect(two_drops)
    assert [f["kind"] for f in flags] == ["price_laddering"]
    assert flags[0]["evidence"]["drops"] == 2


def test_rise_resets_the_ladder() -> None:
    zigzag = _listing(price_history=[["t1", 3000], ["t2", 2900],
                                     ["t3", 3100], ["t4", 3000]])
    assert detect(zigzag) == []
