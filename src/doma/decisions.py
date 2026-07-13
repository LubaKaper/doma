"""Human decisions as validated input events. The UI stays a thin shell."""
from __future__ import annotations

from doma.events import Event
from doma.scorer import DEFAULT_WEIGHTS

MARKABLE_STATUSES = frozenset({"active", "rejected", "pursuing", "viewed"})
VERDICTS = frozenset({"pursue", "pass"})
CRITERIA = frozenset(DEFAULT_WEIGHTS)


def mark_listing_event(listing_id: str, status: str, ts: str) -> Event:
    """The user marks a listing rejected / pursuing / viewed (or reactivates)."""
    if status not in MARKABLE_STATUSES:
        raise ValueError(f"unknown status: {status!r} "
                         f"(allowed: {sorted(MARKABLE_STATUSES)})")
    return Event(ts=ts, type="listing_marked",
                 payload={"listing_id": listing_id, "status": status})


def scorecard_event(listing_id: str, verdict: str,
                    ratings: dict[str, int], ts: str) -> Event:
    """Post-viewing scorecard: overall verdict + 1-5 per experienced criterion."""
    if verdict not in VERDICTS:
        raise ValueError(f"unknown verdict: {verdict!r} "
                         f"(allowed: {sorted(VERDICTS)})")
    for criterion, rating in ratings.items():
        if criterion not in CRITERIA:
            raise ValueError(f"unknown criterion: {criterion!r}")
        if not isinstance(rating, int) or not 1 <= rating <= 5:
            raise ValueError(f"rating for {criterion} must be 1..5, "
                             f"got {rating!r}")
    return Event(ts=ts, type="viewing_scored",
                 payload={"listing_id": listing_id, "verdict": verdict,
                          "ratings": ratings})


def weights_updated_event(weights: dict[str, float],
                          previous: dict[str, float],
                          evidence: dict, ts: str) -> Event:
    """Approved weight update. Validates the table before it becomes truth."""
    if set(weights) != CRITERIA:
        raise ValueError(f"weights must cover exactly the criteria "
                         f"{sorted(CRITERIA)}")
    if any(w < 0 for w in weights.values()):
        raise ValueError("weights must be non-negative")
    if abs(sum(weights.values()) - 1.0) > 1e-6:
        raise ValueError(f"weights must sum to 1, got {sum(weights.values())}")
    return Event(ts=ts, type="weights_updated",
                 payload={"weights": weights, "previous": previous,
                          "evidence": evidence})
