from doma.scorer import (DEFAULT_WEIGHTS, neighborhood_median_price,
                         score_listing, subscore_building_health,
                         subscore_commute, subscore_fee, subscore_rent_value)
from doma.state import ListingState, project
from helpers import ev


def _listing(lid="x", hood="11222", price=3000, **kw) -> ListingState:
    base = dict(listing_id=lid, source="rentcast", neighborhood=hood,
                price=price, status="active",
                first_seen_ts="2026-07-01T09:00:00+00:00",
                last_seen_ts="2026-07-01T09:00:00+00:00")
    base.update(kw)
    return ListingState(**base)


def _state_with_market(prices: list[int]) -> "object":
    events = [ev(f"2026-07-01T09:00:0{i%10}+00:00", "listing_seen",
                 listing_id=f"m-{i}", source="rentcast",
                 neighborhood="11222", price=p)
              for i, p in enumerate(prices)]
    return project(events)


def test_median_needs_five_samples() -> None:
    assert neighborhood_median_price(_state_with_market([3000] * 4), "11222") is None
    assert neighborhood_median_price(
        _state_with_market([2800, 2900, 3000, 3100, 3200]), "11222") == 3000


def test_rent_value_cheaper_is_better() -> None:
    assert subscore_rent_value(3000, 3000) == 0.5
    assert subscore_rent_value(2400, 3000) == 0.7
    assert subscore_rent_value(6000, 3000) == 0.0
    assert subscore_rent_value(None, 3000) is None
    assert subscore_rent_value(3000, None) is None


def test_commute_walk_bands() -> None:
    assert subscore_commute({"walk_meters": 200}) == 1.0
    assert subscore_commute({"walk_meters": 900}) == 0.5
    assert subscore_commute({"walk_meters": 2000}) == 0.0
    assert subscore_commute(None) is None


def test_building_health_penalizes_class_c() -> None:
    clean = subscore_building_health({"class_a": 0, "class_b": 0, "class_c": 0})
    bad_c = subscore_building_health({"class_a": 0, "class_b": 0, "class_c": 5})
    bad_a = subscore_building_health({"class_a": 5, "class_b": 0, "class_c": 0})
    assert clean == 1.0
    assert bad_c < bad_a < clean
    assert subscore_building_health(None) is None


def test_fee_subscore() -> None:
    assert subscore_fee(False) == 1.0
    assert subscore_fee(True) == 0.2
    assert subscore_fee(None) is None


def test_score_renormalizes_over_known_weights() -> None:
    state = _state_with_market([2800, 2900, 3000, 3100, 3200])
    listing = _listing(price=3000, fee=False,
                       commute={"walk_meters": 300},
                       hpd={"class_a": 0, "class_b": 0, "class_c": 0})
    result = score_listing(listing, state, DEFAULT_WEIGHTS)
    # Known: rent_value(.5), commute(1), health(1), fee(1); laundry/light unknown
    known_w = 0.30 + 0.25 + 0.20 + 0.05
    expected = (0.30 * 0.5 + 0.25 * 1 + 0.20 * 1 + 0.05 * 1) / known_w
    assert abs(result.score - expected) < 1e-9
    assert abs(result.confidence - known_w / 1.0) < 1e-9
    assert result.subscores["laundry"] is None


def test_score_none_when_nothing_known() -> None:
    listing = _listing(price=None, fee=None)
    result = score_listing(listing, project([]), DEFAULT_WEIGHTS)
    assert result is None
