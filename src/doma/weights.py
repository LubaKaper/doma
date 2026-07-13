"""Criterion weights: the taste model. Changed only via approved diffs."""
from __future__ import annotations

DEFAULT_WEIGHTS: dict[str, float] = {
    "rent_value": 0.30,
    "commute": 0.25,
    "building_health": 0.20,
    "laundry": 0.10,
    "light": 0.10,
    "fee_burden": 0.05,
}
