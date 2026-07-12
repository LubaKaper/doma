"""RentCast adapter: official API -> Snapshots. The only paid-quota source.

Field names follow developers.rentcast.io/reference/property-listings-schema
(verified 2026-07-11). The monthly call budget is enforced by the policy
engine, not here.
"""
from __future__ import annotations

import requests

from doma.snapshot import Snapshot

BASE_URL = "https://api.rentcast.io/v1/listings/rental/long-term"


def fetch_listings(api_key: str, city: str, state: str,
                   limit: int = 500) -> list[dict]:
    """One API call: active rental listings for a city. Costs quota."""
    try:
        response = requests.get(
            BASE_URL,
            headers={"X-Api-Key": api_key, "Accept": "application/json"},
            params={"city": city, "state": state, "status": "Active",
                    "limit": limit},
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"RentCast request failed for {city}, {state}: "
                           f"{exc}") from exc
    body = response.json()
    if not isinstance(body, list):
        raise RuntimeError(f"RentCast returned unexpected shape "
                           f"(expected list): {type(body).__name__}")
    return body


def to_snapshot(raw: dict) -> Snapshot:
    """Map one documented RentCast listing object to a Snapshot."""
    for required in ("id", "addressLine1", "zipCode"):
        if not raw.get(required):
            raise ValueError(f"RentCast listing missing {required}: "
                             f"{raw.get('id', '<no id>')}")
    baths = raw.get("bathrooms")
    return Snapshot(
        source="rentcast",
        source_id=raw["id"],
        address_line1=raw["addressLine1"],
        unit=raw.get("addressLine2"),
        neighborhood=raw["zipCode"],
        price=raw.get("price"),
        beds=raw.get("bedrooms"),
        baths=float(baths) if baths is not None else None,
        sqft=raw.get("squareFootage"),
        url=None,                    # RentCast does not expose a listing URL
        fee=None,                    # no fee data in this source
        days_on_market=raw.get("daysOnMarket"),
        listed_date=raw.get("listedDate"),
    )
