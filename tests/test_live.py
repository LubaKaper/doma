from datetime import datetime, timezone

from doma.clock import ReplayClock
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
