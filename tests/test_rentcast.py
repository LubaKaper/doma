import json
from pathlib import Path

import pytest

from doma.adapters.rentcast import to_snapshot

FIXTURE = Path(__file__).parent / "fixtures" / "rentcast_sample.json"


def _raw(index: int) -> dict:
    return json.loads(FIXTURE.read_text())["listings"][index]


def test_to_snapshot_maps_documented_fields() -> None:
    # Assert against whatever the (re-capturable) fixture contains, so a
    # fresh real capture never breaks the mapping contract.
    raw = _raw(0)
    snap = to_snapshot(raw)
    assert snap.source == "rentcast"
    assert snap.source_id == raw["id"]
    assert snap.address_line1 == raw["addressLine1"]
    assert snap.unit == raw.get("addressLine2")
    assert snap.neighborhood == raw["zipCode"]  # zip = v1 neighborhood proxy
    assert snap.price == raw.get("price")
    assert snap.beds == raw.get("bedrooms")
    assert snap.days_on_market == raw.get("daysOnMarket")


def test_to_snapshot_missing_fields_stay_none() -> None:
    minimal = {"id": "x-1", "addressLine1": "1 Main St", "zipCode": "11222"}
    snap = to_snapshot(minimal)
    assert snap.unit is None
    assert snap.price is None
    assert snap.sqft is None
    assert snap.fee is None  # RentCast has no fee field; never fabricate


def test_to_snapshot_missing_required_field_raises() -> None:
    broken = _raw(0)
    del broken["addressLine1"]
    with pytest.raises(ValueError, match="addressLine1"):
        to_snapshot(broken)


def test_to_snapshot_carries_coordinates() -> None:
    raw = _raw(0)
    snap = to_snapshot(raw)
    assert snap.lat == raw.get("latitude")
    assert snap.lon == raw.get("longitude")


def test_history_extracted_as_prior_sightings() -> None:
    from doma.adapters.rentcast import history_entries
    raw = {
        "id": "x", "addressLine1": "2971 Shell Rd", "zipCode": "11224",
        "history": {
            "2026-06-09": {"event": "Rental Listing", "price": 3300,
                           "listedDate": "2026-06-09T00:00:00.000Z",
                           "removedDate": "2026-06-10T00:00:00.000Z"},
            "2026-07-13": {"event": "Rental Listing", "price": 3450,
                           "listedDate": "2026-07-13T00:00:00.000Z",
                           "removedDate": None},
        },
    }
    entries = history_entries(raw)
    # chronological, [date, price, was_removed]
    assert entries == [["2026-06-09", 3300, True], ["2026-07-13", 3450, False]]


def test_history_missing_or_empty_is_empty_list() -> None:
    from doma.adapters.rentcast import history_entries
    assert history_entries({"id": "x"}) == []
