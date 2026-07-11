"""Snapshot: the one normalized shape every source adapter emits.

Unknown facts are None — never imputed, never defaulted (TDD.md hard rule).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Snapshot:
    """One listing as one source saw it at one moment."""

    source: str              # "rentcast" | "streeteasy_email"
    source_id: str           # the source's own id for this listing
    address_line1: str       # street address, e.g. "1208 Clay Ave"
    unit: str | None         # apartment/unit, e.g. "4N"
    neighborhood: str        # zip code in v1 (RentCast has no neighborhoods)
    price: int | None
    beds: int | None
    baths: float | None
    sqft: int | None
    url: str | None
    fee: bool | None         # broker fee; None = unknown
    days_on_market: int | None
    listed_date: str | None  # ISO 8601 or None

    def __post_init__(self) -> None:
        if not self.source:
            raise ValueError("Snapshot.source must be non-empty")
        if not self.source_id:
            raise ValueError("Snapshot.source_id must be non-empty")
        if not self.address_line1:
            raise ValueError("Snapshot.address_line1 must be non-empty")
        if not self.neighborhood:
            raise ValueError("Snapshot.neighborhood must be non-empty")
