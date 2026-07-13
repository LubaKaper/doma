"""HPD open-violations enricher via NYC Open Data (Socrata csn4-vhvf).

Field names verified against a live query 2026-07-11: housenumber,
streetname, boro, class, currentstatus. Free API; no key required for
low-volume use.
"""
from __future__ import annotations

import requests

from doma.events import Event
from doma.resolver import normalize_street

DATASET_URL = "https://data.cityofnewyork.us/resource/csn4-vhvf.json"

_ZIP_PREFIX_TO_BORO = {
    "100": "MANHATTAN", "101": "MANHATTAN", "102": "MANHATTAN",
    "103": "STATEN ISLAND", "104": "BRONX", "110": "QUEENS",
    "111": "QUEENS", "112": "BROOKLYN", "113": "QUEENS",
    "114": "QUEENS", "116": "QUEENS",
}


def borough_from_zip(zip_code: str) -> str | None:
    """NYC borough from a zip prefix; None outside the five boroughs."""
    return _ZIP_PREFIX_TO_BORO.get(zip_code[:3])


def fetch_open_violations(housenumber: str, street: str,
                          boro: str) -> list[dict]:
    """Query open HPD violations for one building."""
    params = {
        "housenumber": housenumber,
        "streetname": normalize_street(street).upper(),
        "boro": boro.upper(),
        "$limit": "500",
    }
    try:
        response = requests.get(DATASET_URL, params=params, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"HPD query failed for {housenumber} {street}, "
                           f"{boro}: {exc}") from exc
    return response.json()


def summarize(violations: list[dict]) -> dict:
    """Count open violations by hazard class (A/B/C).

    An empty result is AMBIGUOUS: it can mean a clean building or an
    address that didn't match the dataset — `matched` records which, and
    the scorer treats unmatched as unknown rather than perfect.
    """
    counts = {"class_a": 0, "class_b": 0, "class_c": 0}
    for v in violations:
        key = f"class_{v.get('class', '').lower()}"
        if key in counts:
            counts[key] += 1
    return {**counts, "total": len(violations),
            "matched": len(violations) > 0}


def to_enrichment_event(listing_id: str, summary: dict[str, int],
                        ts: str) -> Event:
    """Wrap a violation summary as an enrichment_added input event."""
    return Event(ts=ts, type="enrichment_added",
                 payload={"listing_id": listing_id,
                          "kind": "hpd_violations", **summary})
