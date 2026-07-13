"""MTA station index: nearest-station walk distance for commute facts.

Stations come from a committed capture of the data.ny.gov subway-stations
dataset 39hk-dx4f (fields verified live 2026-07-13: stop_name,
daytime_routes, gtfs_latitude, gtfs_longitude). Static data, refreshed
manually via scripts/capture_stations.py.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

EARTH_RADIUS_M = 6_371_000


@dataclass(frozen=True)
class Station:
    """One subway station with the routes that stop there."""

    name: str
    routes: frozenset[str]
    lat: float
    lon: float


def load_stations(path: str | Path) -> list[Station]:
    """Load the captured station dataset into Station records."""
    p = Path(path)
    try:
        records = json.loads(p.read_text())
    except OSError as exc:
        raise RuntimeError(f"failed to read stations file {p}: {exc}") from exc
    stations: list[Station] = []
    for r in records:
        stations.append(Station(
            name=r["stop_name"],
            routes=frozenset(r.get("daytime_routes", "").split()),
            lat=float(r["gtfs_latitude"]),
            lon=float(r["gtfs_longitude"]),
        ))
    return stations


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2)
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def nearest_station(lat: float, lon: float, stations: list[Station],
                    routes: frozenset[str] | None = None
                    ) -> tuple[Station, float]:
    """Closest station (optionally limited to given routes) and meters away."""
    candidates = [s for s in stations
                  if routes is None or s.routes & routes]
    if not candidates:
        raise ValueError(f"no stations serve routes {sorted(routes or [])}")
    best = min(candidates,
               key=lambda s: _haversine_m(lat, lon, s.lat, s.lon))
    return best, _haversine_m(lat, lon, best.lat, best.lon)
