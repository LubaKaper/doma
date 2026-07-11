"""Identity resolution: one apartment = one canonical id across sources.

Relist detection depends on this: the same unit reappearing under a new
source id maps to the same canonical id, so the projection sees a dead
listing come back to life (state.py counts that as a relist).
"""
from __future__ import annotations

import re

from doma.snapshot import Snapshot

_ABBREVIATIONS = {
    "st": "street", "ave": "avenue", "av": "avenue", "blvd": "boulevard",
    "rd": "road", "dr": "drive", "pl": "place", "ln": "lane", "ct": "court",
    "sq": "square", "pkwy": "parkway", "hwy": "highway", "ter": "terrace",
    "e": "east", "w": "west", "n": "north", "s": "south",
}


def normalize_street(street: str) -> str:
    """Lowercase, strip punctuation, expand abbreviations, collapse spaces."""
    cleaned = re.sub(r"[^\w\s]", " ", street.lower())
    words = [_ABBREVIATIONS.get(w, w) for w in cleaned.split()]
    return " ".join(words)


def identity_key(address_line1: str, unit: str | None,
                 fallback: str = "") -> str:
    """Stable key for one apartment: normalized address + unit.

    When the unit is unknown, the fallback (source:source_id) keeps distinct
    unit-less listings at the same address from silently merging.
    """
    street_slug = normalize_street(address_line1).replace(" ", "-")
    if unit is not None and unit.strip():
        cleaned = re.sub(r"[^\w]", "", unit.lower())
        # "apt 4n" / "#4n" / "unit 4n" are the same apartment across sources.
        unit_slug = re.sub(r"^(apt|unit|no)", "", cleaned) or cleaned
    else:
        unit_slug = fallback
    return f"{street_slug}::{unit_slug}"


def canonical_id(snapshot: Snapshot) -> str:
    """Canonical listing id for a snapshot (cross-source stable)."""
    return identity_key(snapshot.address_line1, snapshot.unit,
                        fallback=f"{snapshot.source}:{snapshot.source_id}")
