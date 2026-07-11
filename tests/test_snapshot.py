import pytest

from doma.snapshot import Snapshot


def _snap(**overrides) -> Snapshot:
    base = dict(source="rentcast", source_id="rc-1",
                address_line1="1208 Clay Ave", unit="4N",
                neighborhood="10456", price=2400, beds=2, baths=1.0,
                sqft=850, url=None, fee=None, days_on_market=12,
                listed_date="2026-07-01T00:00:00+00:00")
    base.update(overrides)
    return Snapshot(**base)


def test_snapshot_holds_fields() -> None:
    s = _snap()
    assert s.source == "rentcast"
    assert s.unit == "4N"
    assert s.fee is None  # unknown stays None, never defaulted


def test_snapshot_requires_source_and_address() -> None:
    with pytest.raises(ValueError, match="source"):
        _snap(source="")
    with pytest.raises(ValueError, match="address_line1"):
        _snap(address_line1="")


def test_snapshot_is_immutable() -> None:
    s = _snap()
    with pytest.raises(AttributeError):
        s.price = 9999  # type: ignore[misc]
