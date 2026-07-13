from datetime import datetime, timezone

from doma.clock import ReplayClock
from doma.events import Event
from doma.live import LiveExecutor
from doma.policy import Action
from doma.snapshot import Snapshot
from doma.store import EventStore


def _snap() -> Snapshot:
    return Snapshot(source="rentcast", source_id="rc-1",
                    address_line1="55 Nassau Ave", unit=None,
                    neighborhood="11222", price=3100, beds=1, baths=1.0,
                    sqft=None, url=None, fee=None, days_on_market=5,
                    listed_date=None)


def _executor(store: EventStore, snapshots: list[Snapshot]) -> LiveExecutor:
    # fetcher is injected so tests never touch the network (TDD.md hard rule).
    return LiveExecutor(store=store,
                        fetcher=lambda: snapshots,
                        clock=ReplayClock(
                            start=datetime(2026, 7, 10, tzinfo=timezone.utc)),
                        sleep_seconds=0)


def test_scan_action_fetches_diffs_and_bookkeeps() -> None:
    store = EventStore(":memory:")
    executor = _executor(store, [_snap()])
    events = executor.execute(Action(type="scan_rentcast", target=None,
                                     reason="test"))
    assert [e.type for e in events] == ["listing_seen", "budget_spent",
                                        "scan_completed"]
    assert events[0].payload["neighborhood"] == "11222"


def test_mark_saturated_matches_replay_semantics() -> None:
    store = EventStore(":memory:")
    executor = _executor(store, [])
    events = executor.execute(Action(type="mark_saturated",
                                     target="11222", reason="test"))
    assert [e.type for e in events] == ["neighborhood_saturated"]
    assert events[0].payload == {"neighborhood": "11222"}


def test_sleep_returns_no_events() -> None:
    store = EventStore(":memory:")
    executor = _executor(store, [])
    assert executor.execute(Action(type="sleep", target=None,
                                   reason="test")) == []


def test_enrich_batch_with_injected_enrichers() -> None:
    store = EventStore(":memory:")
    store.append(Event(ts="2026-07-10T00:00:00+00:00", type="listing_seen",
                       payload={"listing_id": "a", "source": "rentcast",
                                "neighborhood": "11222", "price": 3000,
                                "address": "55 Nassau Ave",
                                "lat": 40.72, "lon": -73.95}))

    def fake_hpd(listing):
        return {"class_a": 1, "class_b": 0, "class_c": 0, "total": 1}

    def broken_commute(listing):
        raise RuntimeError("stations file missing")

    executor = LiveExecutor(store=store, fetcher=lambda: [],
                            clock=ReplayClock(
                                start=datetime(2026, 7, 10, tzinfo=timezone.utc)),
                            sleep_seconds=0,
                            hpd_fetch=fake_hpd, commute_fn=broken_commute)
    events = executor.execute(Action(type="enrich_batch", target=None,
                                     reason="t", targets=("a",)))
    types = [e.type for e in events]
    assert types == ["enrichment_added", "enrichment_attempted"]
    attempted = events[-1].payload
    assert attempted["ok"] is False
    assert "stations file missing" in attempted["errors"][0]


def test_score_batch_scores_from_state() -> None:
    store = EventStore(":memory:")
    for i, price in enumerate([2800, 2900, 3000, 3100, 3200]):
        store.append(Event(ts="2026-07-10T00:00:00+00:00", type="listing_seen",
                           payload={"listing_id": f"m-{i}", "source": "rentcast",
                                    "neighborhood": "11222", "price": price,
                                    "fee": False}))
    executor = LiveExecutor(store=store, fetcher=lambda: [],
                            clock=ReplayClock(
                                start=datetime(2026, 7, 10, tzinfo=timezone.utc)),
                            sleep_seconds=0)
    events = executor.execute(Action(type="score_batch", target=None,
                                     reason="t", targets=("m-0",)))
    assert events[0].type == "score_computed"
    assert events[0].payload["score"] is not None
    assert 0 < events[0].payload["confidence"] < 1
