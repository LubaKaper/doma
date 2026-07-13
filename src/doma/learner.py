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


def propose_weights(state: HuntState) -> Proposal | None:
    """Bounded, renormalized weight proposal — or None if nothing to say."""
    current = dict(state.weights)
    ratings = collect_ratings(state)
    evidence: dict[str, Any] = {}
    proposed = dict(current)
    for criterion, rs in ratings.items():
        if criterion not in current or len(rs) < MIN_RATINGS:
            continue
        salience = _salience(rs)
        # salience 0.5 is the pivot: extreme reactions push the weight up,
        # indifference pushes it down; capped either way.
        step = max(-MAX_STEP, min(MAX_STEP, 2 * MAX_STEP * (salience - 0.5)))
        proposed[criterion] = max(WEIGHT_FLOOR, current[criterion] + step)
        evidence[criterion] = {"ratings": rs, "salience": round(salience, 3),
                               "step": round(step, 4)}
    if not evidence:
        return None
    total = sum(proposed.values())
    normalized = {k: v / total for k, v in proposed.items()}
    if all(abs(normalized[k] - current[k]) < MIN_MEANINGFUL_DELTA
           for k in current):
        return None
    return Proposal(weights=normalized, previous=current, evidence=evidence)
