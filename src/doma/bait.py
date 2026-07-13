"""Bait detection: deterministic rules over listing history, with evidence.

Every flag carries the evidence that triggered it — no vibes, no LLM.
"""
from __future__ import annotations

from typing import Any

from doma.state import ListingState

LADDER_MIN_DROPS = 2


def _consecutive_drops(history: list[list[Any]]) -> int:
    """Longest run of consecutive price drops ending at the latest price."""
    drops = 0
    for i in range(len(history) - 1, 0, -1):
        if history[i][1] < history[i - 1][1]:
            drops += 1
        else:
            break
    return drops


def detect(listing: ListingState) -> list[dict[str, Any]]:
    """All bait flags for one listing: kind + evidence dicts."""
    flags: list[dict[str, Any]] = []
    if listing.relist_count >= 1:
        flags.append({
            "kind": "relist",
            "evidence": {"relist_count": listing.relist_count,
                         "price_history": listing.price_history},
        })
    drops = _consecutive_drops(listing.price_history)
    if drops >= LADDER_MIN_DROPS:
        flags.append({
            "kind": "price_laddering",
            "evidence": {"drops": drops,
                         "price_history": listing.price_history},
        })
    # fee_contradiction is reserved: fires when extracted facts claim
    # "no fee" while the structured fee field is True (needs email facts).
    return flags
