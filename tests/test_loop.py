from datetime import datetime, timezone

from helpers import ev

from doma.clock import ReplayClock
from doma.events import Event
from doma.loop import run_tick
from doma.policy import Action, PolicyConfig
from doma.store import EventStore


class FakeExecutor:
    """Records the action it received; returns canned events."""

    def __init__(self, events: list[Event]) -> None:
        self.seen: list[Action] = []
        self._events = events

    def execute(self, action: Action) -> list[Event]:
        self.seen.append(action)
        return self._events


def test_run_tick_projects_decides_executes_appends() -> None:
    store = EventStore(":memory:")
    clock = ReplayClock(start=datetime(2026, 7, 1, tzinfo=timezone.utc))
    canned = [ev("2026-07-01T00:00:00+00:00", "scan_completed", source="rentcast"),
              ev("2026-07-01T00:00:00+00:00", "budget_spent",
                 resource="rentcast_scan")]
    executor = FakeExecutor(canned)

    action, new_events = run_tick(store, PolicyConfig(), executor, clock)

    # Empty store -> scan is due -> policy decides scan_rentcast.
    assert action.type == "scan_rentcast"
    assert executor.seen == [action]
    # Executor's events were appended with assigned seqs.
    stored = store.read_all()
    assert [e.type for e in stored] == ["scan_completed", "budget_spent"]
    assert [e.seq for e in stored] == [1, 2]
    assert [e.seq for e in new_events] == [1, 2]


def test_second_tick_sees_first_ticks_events() -> None:
    store = EventStore(":memory:")
    clock = ReplayClock(start=datetime(2026, 7, 1, tzinfo=timezone.utc))
    canned = [ev("2026-07-01T00:00:00+00:00", "scan_completed", source="rentcast"),
              ev("2026-07-01T00:00:00+00:00", "budget_spent",
                 resource="rentcast_scan")]
    run_tick(store, PolicyConfig(), FakeExecutor(canned), clock)

    action, _ = run_tick(store, PolicyConfig(), FakeExecutor([]), clock)
    # Scan just happened and clock hasn't moved -> nothing to do.
    assert action.type == "sleep"
