"""Test helpers shared across test modules."""
from typing import Any

from doma.events import Event


def ev(ts: str, type: str, **payload: Any) -> Event:
    """Build an Event with keyword payload fields."""
    return Event(ts=ts, type=type, payload=payload)
