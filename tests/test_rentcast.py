import json
from pathlib import Path

import pytest

from doma.adapters.rentcast import to_snapshot

FIXTURE = Path(__file__).parent / "fixtures" / "rentcast_sample.json"


def _raw(index: int) -> dict:
    return json.loads(FIXTURE.read_text())["listings"][index]


def test_to_snapshot_maps_documented_fields() -> None:
    snap = to_snapshot(_raw(0))
    assert snap.source == "rentcast"
    assert snap.source_id == "1208-Clay-Ave,-Apt-4N,-Bronx,-NY-10456"
    assert snap.address_line1 == "1208 Clay Ave"
    assert snap.unit == "Apt 4N"
    assert snap.neighborhood == "10456"  # zip is the v1 neighborhood proxy
    assert snap.price == 2400
    assert snap.beds == 2
    assert snap.days_on_market == 12


def test_to_snapshot_missing_fields_stay_none() -> None:
    snap = to_snapshot(_raw(1))
    assert snap.unit is None
    assert snap.sqft is None
    assert snap.fee is None  # RentCast has no fee field; never fabricate


def test_to_snapshot_missing_required_field_raises() -> None:
    broken = _raw(0)
    del broken["addressLine1"]
    with pytest.raises(ValueError, match="addressLine1"):
        to_snapshot(broken)
