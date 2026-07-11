"""Decision policy: pure functions that pick the next action each tick.

This module is the spec's centerpiece: every stopping rule is a named,
individually tested predicate; decide() is a deterministic priority ladder.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from doma.events import parse_ts
from doma.state import TERMINAL_STATUSES, HuntState, ListingState


@dataclass(frozen=True)
class PolicyConfig:
    """Tunable thresholds. No magic numbers outside this class."""

    scan_interval_hours: int = 24
    monthly_scan_cap: int = 40
    saturation_days: int = 7


@dataclass(frozen=True)
class Action:
    """One decision. type is one of: scan_rentcast | mark_saturated | sleep."""

    type: str
    target: str | None
    reason: str


def is_terminal(listing: ListingState) -> bool:
    """Stopping rule: terminal listings cost zero future actions."""
    return listing.status in TERMINAL_STATUSES


def budget_exhausted(state: HuntState, now: datetime, config: PolicyConfig) -> bool:
    """Stopping rule: hard cap on RentCast scans per calendar month."""
    month = now.strftime("%Y-%m")
    return state.scan_months.get(month, 0) >= config.monthly_scan_cap


def scan_due(state: HuntState, now: datetime, config: PolicyConfig) -> bool:
    """A scan is due if none has ever run, or the interval has elapsed."""
    if state.last_scan_ts is None:
        return True
    elapsed = now - parse_ts(state.last_scan_ts)
    return elapsed >= timedelta(hours=config.scan_interval_hours)


def stale_neighborhoods(state: HuntState, now: datetime,
                        config: PolicyConfig) -> list[str]:
    """Stopping rule: neighborhoods with no novel inventory in the window.

    Returns unsaturated neighborhoods, sorted for determinism.
    """
    window = timedelta(days=config.saturation_days)
    return sorted(
        hood
        for hood, ts in state.last_novel_ts.items()
        if hood not in state.saturated and now - parse_ts(ts) >= window
    )


def decide(state: HuntState, now: datetime, config: PolicyConfig) -> Action:
    """Deterministic priority ladder. Pure: same inputs, same action."""
    stale = stale_neighborhoods(state, now, config)
    if stale:
        return Action(type="mark_saturated", target=stale[0],
                      reason=f"no novel inventory in {config.saturation_days} days")
    if scan_due(state, now, config):
        if budget_exhausted(state, now, config):
            return Action(type="sleep", target=None,
                          reason="scan due but monthly budget exhausted")
        return Action(type="scan_rentcast", target=None,
                      reason="scan interval elapsed")
    return Action(type="sleep", target=None, reason="nothing to do")
