"""Plain-language translations of Doma's numbers. Pure and tested."""
from __future__ import annotations

from typing import Any

WALK_METERS_PER_MIN = 80

BAIT_LABELS = {
    "too_good_to_be_true": "price looks too good to be true",
    "relist": "relisted recently — possible bait",
    "price_laddering": "price keeps dropping",
    "fee_contradiction": "fee claims don't add up",
}


def fit_label(score: float | None) -> str:
    """A verdict a person can read."""
    if score is None:
        return "Not assessed yet"
    if score >= 0.8:
        return "Strong fit"
    if score >= 0.65:
        return "Good fit"
    if score >= 0.45:
        return "Fair fit"
    return "Weak fit"


def knowledge_label(confidence: float | None) -> str:
    """How much of the assessment rests on real facts."""
    if confidence is None or confidence < 0.35:
        return "we know little about it so far"
    if confidence < 0.65:
        return "we know some things about it"
    return "we know a lot about it"


def walk_label(commute: dict[str, Any] | None) -> str | None:
    if not commute or commute.get("walk_meters") is None:
        return None
    minutes = max(1, round(commute["walk_meters"] / WALK_METERS_PER_MIN))
    station = commute.get("station", "the subway")
    return f"≈{minutes} min walk to {station}"


def fee_label(fee: bool | None) -> str | None:
    if fee is False:
        return "no broker fee"
    if fee is True:
        return "broker fee"
    return None  # unknown -> say nothing rather than noise


def building_label(hpd: dict[str, Any] | None) -> str | None:
    if not hpd or (hpd.get("matched") is not True
                   and hpd.get("total", 0) == 0):
        return None  # unknown record -> silence, not false reassurance
    total = hpd.get("total", 0)
    serious = hpd.get("class_c", 0)
    if total == 0:
        return "clean building record"
    label = f"{total} open violation{'s' if total != 1 else ''}"
    if serious:
        label += f" ({serious} serious)"
    return label


def chips(listing: Any) -> list[str]:
    """The 2-4 facts worth putting on a card."""
    out = []
    for label in (walk_label(listing.commute), fee_label(listing.fee),
                  building_label(listing.hpd)):
        if label:
            out.append(label)
    return out
