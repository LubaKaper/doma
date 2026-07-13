"""Preference learner: scorecards -> proposed weight diffs. Never self-applies.

v1 signal is salience (ratings-only): criteria the user consistently rates
at the extremes (1-2 or 4-5) matter to them; consistently neutral (3) means
indifference. Proposals are bounded, renormalized, and only ever applied by
an explicit human approval that lands as a weights_updated event.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from doma.state import HuntState

MIN_RATINGS = 3          # scorecards per criterion before proposing
MAX_STEP = 0.03          # max change per criterion per proposal
WEIGHT_FLOOR = 0.02      # no criterion is ever fully silenced
MIN_MEANINGFUL_DELTA = 0.005


@dataclass(frozen=True)
class Proposal:
    """A proposed weight table with the evidence that produced it."""

    weights: dict[str, float]
    previous: dict[str, float]
    evidence: dict[str, Any]


def _salience(ratings: list[int]) -> float:
    """0 = always neutral (3), 1 = always extreme (1 or 5)."""
    return sum(2 * abs((r - 1) / 4 - 0.5) for r in ratings) / len(ratings)


def collect_ratings(state: HuntState) -> dict[str, list[int]]:
    """All scorecard ratings per criterion, from listing scorecards."""
    out: dict[str, list[int]] = {}
    for listing in state.listings.values():
        if listing.scorecard is None:
            continue
        for criterion, rating in listing.scorecard.get("ratings", {}).items():
            out.setdefault(criterion, []).append(rating)
    return out


def _rebalance(current: dict[str, float],
               steps: dict[str, float]) -> dict[str, float] | None:
    """Zero-sum rebalance keeping every invariant by construction.

    Stepped criteria move toward their step (never past it, never inverted);
    unstepped criteria absorb the counterweight, each capped at MAX_STEP and
    floored at WEIGHT_FLOOR. If the absorbers can't take it all, the steps
    are scaled toward zero until the books balance. Sum stays exactly 1.
    """
    net: dict[str, float] = {}
    for c, w in current.items():
        d = steps.get(c, 0.0)
        net[c] = max(d, WEIGHT_FLOOR - w) if d < 0 else d
    surplus = sum(net.values())
    absorbers = [c for c in current if c not in steps]
    for _ in range(len(current) + 1):
        if abs(surplus) < 1e-12 or not absorbers:
            break
        share = -surplus / len(absorbers)
        still_open: list[str] = []
        for c in absorbers:
            lo = max(-MAX_STEP, WEIGHT_FLOOR - current[c])
            clamped = max(lo, min(MAX_STEP, net[c] + share))
            surplus += clamped - net[c]
            net[c] = clamped
            if lo < net[c] < MAX_STEP:
                still_open.append(c)
        absorbers = still_open
    if abs(surplus) > 1e-9:
        stepped_total = sum(net[c] for c in steps)
        if abs(stepped_total) < 1e-12:
            return None
        scale = max(0.0, min(1.0, 1.0 - surplus / stepped_total))
        for c in steps:
            net[c] *= scale
        surplus = sum(net.values())
        if abs(surplus) > 1e-9:
            return None
    return {c: current[c] + net[c] for c in current}


def propose_weights(state: HuntState) -> Proposal | None:
    """Bounded, zero-sum weight proposal — or None if nothing to say."""
    current = dict(state.weights)
    ratings = collect_ratings(state)
    evidence: dict[str, Any] = {}
    steps: dict[str, float] = {}
    for criterion, rs in ratings.items():
        if criterion not in current or len(rs) < MIN_RATINGS:
            continue
        salience = _salience(rs)
        # salience 0.5 is the pivot: extreme reactions push the weight up,
        # indifference pushes it down; capped either way.
        step = max(-MAX_STEP, min(MAX_STEP, 2 * MAX_STEP * (salience - 0.5)))
        steps[criterion] = step
        evidence[criterion] = {"ratings": rs, "salience": round(salience, 3),
                               "step": round(step, 4)}
    if not evidence:
        return None
    proposed = _rebalance(current, steps)
    if proposed is None:
        return None
    if all(abs(proposed[k] - current[k]) < MIN_MEANINGFUL_DELTA
           for k in current):
        return None
    return Proposal(weights=proposed, previous=current, evidence=evidence)
