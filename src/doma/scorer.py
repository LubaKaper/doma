"""Scoring: weighted subscores with confidence from fact completeness.

Every subscore is in [0, 1] or None. Unknown facts stay None — they lower
confidence, never the score (weights renormalize over what is known).
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any

from doma.state import HuntState, ListingState

DEFAULT_WEIGHTS: dict[str, float] = {
    "rent_value": 0.30,
    "commute": 0.25,
    "building_health": 0.20,
    "laundry": 0.10,
    "light": 0.10,
    "fee_burden": 0.05,
}

MEDIAN_MIN_SAMPLES = 5
WALK_BEST_M = 300.0
WALK_WORST_M = 1500.0


@dataclass(frozen=True)
class ScoreResult:
    """One scoring pass over one listing."""

    score: float
    confidence: float
    subscores: dict[str, float | None]


def neighborhood_median_price(state: HuntState, neighborhood: str) -> int | None:
    """Median asking price of active priced listings in one neighborhood."""
    prices = [l.price for l in state.listings.values()
              if l.neighborhood == neighborhood and l.status == "active"
              and l.price is not None]
    if len(prices) < MEDIAN_MIN_SAMPLES:
        return None
    return int(statistics.median(prices))


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def subscore_rent_value(price: int | None, median: int | None) -> float | None:
    """0.5 at the neighborhood median; better when cheaper."""
    if price is None or median is None or median <= 0:
        return None
    return _clamp(0.5 + (median - price) / median)


def subscore_commute(commute: dict[str, Any] | None) -> float | None:
    """1.0 within a short walk of a station, 0.0 beyond a long one."""
    if commute is None or commute.get("walk_meters") is None:
        return None
    walk = float(commute["walk_meters"])
    if walk <= WALK_BEST_M:
        return 1.0
    if walk >= WALK_WORST_M:
        return 0.0
    return _clamp(1.0 - (walk - WALK_BEST_M) / (WALK_WORST_M - WALK_BEST_M))


def subscore_building_health(hpd: dict[str, Any] | None) -> float | None:
    """Open HPD violations, class C weighted heaviest."""
    if hpd is None:
        return None
    burden = (0.1 * hpd.get("class_a", 0) + 0.3 * hpd.get("class_b", 0)
              + 0.6 * hpd.get("class_c", 0))
    return 1.0 / (1.0 + burden)


def subscore_fee(fee: bool | None) -> float | None:
    """No-fee is a big win; a fee is a real cost; unknown stays unknown."""
    if fee is None:
        return None
    return 1.0 if fee is False else 0.2


def subscore_laundry(listing: ListingState) -> float | None:
    """Needs extracted facts (email/text sources) — None until then."""
    return None


def subscore_light(listing: ListingState) -> float | None:
    """Needs extracted facts (floor/exposure) — None until then."""
    return None


def score_listing(listing: ListingState, state: HuntState,
                  weights: dict[str, float]) -> ScoreResult | None:
    """Score one listing; None when no subscore is knowable at all."""
    subscores: dict[str, float | None] = {
        "rent_value": subscore_rent_value(
            listing.price,
            neighborhood_median_price(state, listing.neighborhood)),
        "commute": subscore_commute(listing.commute),
        "building_health": subscore_building_health(listing.hpd),
        "laundry": subscore_laundry(listing),
        "light": subscore_light(listing),
        "fee_burden": subscore_fee(listing.fee),
    }
    known = {k: v for k, v in subscores.items() if v is not None}
    if not known:
        return None
    known_weight = sum(weights[k] for k in known)
    score = sum(weights[k] * v for k, v in known.items()) / known_weight
    confidence = known_weight / sum(weights.values())
    return ScoreResult(score=score, confidence=confidence, subscores=subscores)
