from datetime import datetime, timedelta, timezone
from pathlib import Path

from helpers import ev

from doma.clock import ReplayClock
from doma.corpus import load_corpus
from doma.policy import Action, PolicyConfig
from doma.replay import ReplayExecutor, run_replay
from doma.state import project
from doma.store import EventStore

FIXTURE = Path(__file__).parent / "fixtures" / "corpus_smoke.jsonl"


def _clock(day: int = 1, hour: int = 0) -> ReplayClock:
    return ReplayClock(start=datetime(2026, 7, day, hour, tzinfo=timezone.utc),
                       step=timedelta(hours=6))


def test_scan_delivers_due_listing_events_plus_bookkeeping() -> None:
    corpus = [
        ev("2026-07-01T09:00:00+00:00", "listing_seen", listing_id="gp-001",
           source="rentcast", neighborhood="greenpoint", price=3200),
        ev("2026-07-05T09:00:00+00:00", "listing_seen", listing_id="gp-002",
           source="rentcast", neighborhood="greenpoint", price=2900),
    ]
    executor = ReplayExecutor(corpus, _clock(day=2))
    events = executor.execute(Action(type="scan_rentcast", target=None,
                                     reason="test"))
    types = [e.type for e in events]
    # Only the 07-01 listing is due at 07-02; bookkeeping events follow.
    assert types == ["listing_seen", "budget_spent", "scan_completed"]
    assert events[0].payload["listing_id"] == "gp-001"
    assert not executor.exhausted()


def test_scan_does_not_redeliver() -> None:
    corpus = [ev("2026-07-01T09:00:00+00:00", "listing_seen", listing_id="gp-001",
                 source="rentcast", neighborhood="greenpoint", price=3200)]
    executor = ReplayExecutor(corpus, _clock(day=2))
    executor.execute(Action(type="scan_rentcast", target=None, reason="test"))
    events = executor.execute(Action(type="scan_rentcast", target=None,
                                     reason="test"))
    assert [e.type for e in events] == ["budget_spent", "scan_completed"]
    assert executor.exhausted()


def test_sleep_advances_clock() -> None:
    clock = _clock()
    executor = ReplayExecutor([], clock)
    executor.execute(Action(type="sleep", target=None, reason="test"))
    assert clock.now() == datetime(2026, 7, 1, 6, tzinfo=timezone.utc)


def test_mark_saturated_emits_event_at_sim_time() -> None:
    executor = ReplayExecutor([], _clock(day=9))
    events = executor.execute(Action(type="mark_saturated",
                                     target="greenpoint", reason="test"))
    assert len(events) == 1
    assert events[0].type == "neighborhood_saturated"
    assert events[0].payload == {"neighborhood": "greenpoint"}
    assert events[0].ts == "2026-07-09T00:00:00+00:00"


def _run_smoke() -> tuple[list[Action], list]:
    store = EventStore(":memory:")
    clock = ReplayClock(start=datetime(2026, 7, 1, tzinfo=timezone.utc),
                        step=timedelta(hours=6))
    actions = run_replay(store, PolicyConfig(), load_corpus(FIXTURE), clock,
                         until=datetime(2026, 7, 15, tzinfo=timezone.utc))
    return actions, store.read_all()


def test_smoke_corpus_saturation_fires_in_order() -> None:
    _, events = _run_smoke()
    sat = [e for e in events if e.type == "neighborhood_saturated"]
    assert [e.payload["neighborhood"] for e in sat] == ["williamsburg",
                                                        "greenpoint"]
    # Williamsburg saturates >= 7 days after its last novel listing (07-02).
    assert sat[0].ts >= "2026-07-09T10:00:00+00:00"
    # Greenpoint saturates >= 7 days after its last novel listing (07-03).
    assert sat[1].ts >= "2026-07-10T09:00:00+00:00"


def test_smoke_corpus_budget_never_exceeded() -> None:
    actions, events = _run_smoke()
    scans = [a for a in actions if a.type == "scan_rentcast"]
    assert 10 <= len(scans) <= PolicyConfig().monthly_scan_cap
    state = project(events)
    assert all(n <= PolicyConfig().monthly_scan_cap
               for n in state.scan_months.values())


def test_smoke_corpus_final_state() -> None:
    _, events = _run_smoke()
    state = project(events)
    assert set(state.listings) == {"gp-001", "gp-002", "gp-003", "wb-001"}
    assert state.listings["gp-002"].status == "dead"
    assert state.listings["gp-001"].price == 3100
    assert state.saturated == {"greenpoint", "williamsburg"}


def test_replay_is_deterministic() -> None:
    first, _ = _run_smoke()
    second, _ = _run_smoke()
    assert [(a.type, a.target) for a in first] == \
           [(a.type, a.target) for a in second]
