from helpers import ev

from hunt.store import EventStore


def test_append_assigns_increasing_seq() -> None:
    store = EventStore(":memory:")
    e1 = store.append(ev("2026-07-01T09:00:00+00:00", "listing_seen",
                         listing_id="gp-001", source="rentcast",
                         neighborhood="greenpoint", price=3200))
    e2 = store.append(ev("2026-07-01T10:00:00+00:00", "scan_completed",
                         source="rentcast"))
    assert e1.seq == 1
    assert e2.seq == 2


def test_read_all_returns_events_in_append_order() -> None:
    store = EventStore(":memory:")
    store.append(ev("2026-07-02T09:00:00+00:00", "scan_completed", source="rentcast"))
    store.append(ev("2026-07-01T09:00:00+00:00", "listing_seen",
                    listing_id="gp-001", source="rentcast",
                    neighborhood="greenpoint", price=3200))
    events = store.read_all()
    assert [e.seq for e in events] == [1, 2]
    assert events[1].payload["listing_id"] == "gp-001"


def test_payload_survives_round_trip(tmp_path) -> None:
    db = tmp_path / "hunt.db"
    store = EventStore(db)
    store.append(ev("2026-07-01T09:00:00+00:00", "listing_seen",
                    listing_id="gp-001", source="rentcast",
                    neighborhood="greenpoint", price=None))
    reopened = EventStore(db)
    events = reopened.read_all()
    assert events[0].payload["price"] is None
