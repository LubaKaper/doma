from datetime import datetime, timedelta, timezone

from hunt.clock import LiveClock, ReplayClock


def test_replay_clock_starts_at_start() -> None:
    start = datetime(2026, 7, 1, tzinfo=timezone.utc)
    clock = ReplayClock(start=start)
    assert clock.now() == start


def test_replay_clock_advances_by_step() -> None:
    start = datetime(2026, 7, 1, tzinfo=timezone.utc)
    clock = ReplayClock(start=start, step=timedelta(hours=6))
    clock.advance()
    clock.advance()
    assert clock.now() == start + timedelta(hours=12)


def test_live_clock_is_utc_and_advance_is_noop() -> None:
    clock = LiveClock()
    before = clock.now()
    clock.advance()
    assert before.tzinfo is not None
    assert clock.now() >= before
