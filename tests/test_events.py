from datetime import datetime, timezone

import pytest

from hunt.events import Event, from_json, iso, parse_ts, to_json


def test_event_json_round_trip() -> None:
    event = Event(
        ts="2026-07-01T09:00:00+00:00",
        type="listing_seen",
        payload={"listing_id": "gp-001", "source": "rentcast",
                 "neighborhood": "greenpoint", "price": 3200},
    )
    restored = from_json(to_json(event))
    assert restored == event


def test_unknown_event_type_rejected() -> None:
    with pytest.raises(ValueError, match="unknown event type"):
        Event(ts="2026-07-01T09:00:00+00:00", type="not_a_thing", payload={})


def test_iso_and_parse_ts_round_trip() -> None:
    dt = datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc)
    assert iso(dt) == "2026-07-01T09:00:00+00:00"
    assert parse_ts(iso(dt)) == dt


def test_iso_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        iso(datetime(2026, 7, 1, 9, 0))


def test_seq_defaults_to_none() -> None:
    event = Event(ts="2026-07-01T09:00:00+00:00", type="scan_completed",
                  payload={"source": "rentcast"})
    assert event.seq is None
