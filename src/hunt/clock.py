"""Clocks: the only difference between live mode and replay mode."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Protocol


class Clock(Protocol):
    """Time source for the loop."""

    def now(self) -> datetime: ...

    def advance(self) -> None: ...


class LiveClock:
    """Real UTC time; advance() is a no-op because real time moves itself."""

    def now(self) -> datetime:
        """Return the current UTC time."""
        return datetime.now(timezone.utc)

    def advance(self) -> None:
        """No-op: real time advances on its own."""
        return None


class ReplayClock:
    """Simulated time that advances by a fixed step when the loop sleeps."""

    def __init__(self, start: datetime,
                 step: timedelta = timedelta(hours=6)) -> None:
        self._now = start
        self._step = step

    def now(self) -> datetime:
        """Return the current simulated time."""
        return self._now

    def advance(self) -> None:
        """Move simulated time forward by one step."""
        self._now = self._now + self._step
