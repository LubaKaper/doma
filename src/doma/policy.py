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
    enrich_batch_size: int = 20


@dataclass(frozen=True)
class Action:
    """One decision: scan_rentcast | enrich_batch | score_batch |
    mark_saturated | sleep."""

    type: str
    target: str | None
    reason: str
    targets: tuple[str, ...] | None = None


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


def pending_enrichment(state: HuntState) -> list[str]:
    """Active listings never yet enriched, sorted for determinism."""
    return sorted(lid for lid, l in state.listings.items()
                  if l.status == "active" and l.enrich_attempted_ts is None)


def stale_scores(state: HuntState) -> list[str]:
    """Active, enrichment-attempted listings with new activity since scoring."""
    out = []
    for lid, l in state.listings.items():
        if l.status != "active" or l.enrich_attempted_ts is None:
            continue
        last_activity = max(l.last_seen_ts, l.enrich_attempted_ts)
        if (l.score_ts is None or last_activity > l.score_ts
                or (state.weights_ts is not None
                    and l.score_ts < state.weights_ts)):
            out.append(lid)
    return sorted(out)


def decide(state: HuntState, now: datetime, config: PolicyConfig) -> Action:
    """Deterministic priority ladder. Pure: same inputs, same action."""
    stale = stale_neighborhoods(state, now, config)
    if stale:
        return Action(type="mark_saturated", target=stale[0],
                      reason=f"no novel inventory in {config.saturation_days} days")
    to_enrich = pending_enrichment(state)
    if to_enrich:
        batch = tuple(to_enrich[:config.enrich_batch_size])
        return Action(type="enrich_batch", target=None,
                      reason=f"{len(to_enrich)} listings await enrichment",
                      targets=batch)
    to_score = stale_scores(state)
    if to_score:
        return Action(type="score_batch", target=None,
                      reason=f"{len(to_score)} listings need (re)scoring",
                      targets=tuple(to_score))
    if scan_due(state, now, config):
        if budget_exhausted(state, now, config):
            return Action(type="sleep", target=None,
                          reason="scan due but monthly budget exhausted")
        if (state.last_novel_ts
                and set(state.last_novel_ts) <= state.saturated):
            return Action(type="sleep", target=None,
                          reason="all known neighborhoods saturated")
        return Action(type="scan_rentcast", target=None,
                      reason="scan interval elapsed")
    return Action(type="sleep", target=None, reason="nothing to do")
