"""NYC GeoSearch (Pelias) geocoder: address -> zip/borough/coordinates.

Free, keyless, NYC-only (planninglabs.nyc). Used to fill location facts for
sources that report neighborhood names instead of zips (alert emails).
Response fields verified live 2026-07-15: features[].geometry.coordinates
(lon, lat) and properties.postalcode/borough/confidence.
"""
from __future__ import annotations

from typing import Any

import requests

SEARCH_URL = "https://geosearch.planninglabs.nyc/v2/search"
MIN_CONFIDENCE = 0.7


def fetch_geosearch(address: str) -> dict[str, Any]:
    """One geocoding query. Raises with the address named on failure."""
    try:
        response = requests.get(SEARCH_URL,
                                params={"text": address, "size": "1"},
                                timeout=15)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"GeoSearch failed for {address!r}: {exc}") from exc
    return response.json()


def to_geo(pelias: dict[str, Any]) -> dict[str, Any] | None:
    """Best match as {zip, borough, lat, lon, confidence} — or None.

    None when there is no match, low confidence, or no postal code: a bad
    geocode is worse than an honest unknown (this API is NYC-only and will
    fuzzy-match out-of-state addresses badly).
    """
    features = pelias.get("features") or []
    if not features:
        return None
    props = features[0].get("properties", {})
    coords = features[0].get("geometry", {}).get("coordinates")
    confidence = props.get("confidence", 0)
    if confidence < MIN_CONFIDENCE or not props.get("postalcode") or not coords:
        return None
    return {"zip": props["postalcode"], "borough": props.get("borough"),
            "lat": coords[1], "lon": coords[0], "confidence": confidence}
