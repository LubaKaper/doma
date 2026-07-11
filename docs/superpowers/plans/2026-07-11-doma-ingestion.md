# Doma Ingestion Implementation Plan (Plan 2 of 4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Real data flows into the event store — RentCast scans, HPD building-health enrichment, commute distances — with cross-source identity resolution and relist detection, plus a corpus recorder so real captured weeks can replace the synthetic smoke corpus.

**Architecture:** Source adapters normalize raw payloads into one `Snapshot` shape; a pure differ compares snapshots against projected state and emits the input events Plan 1 already replays; a `LiveExecutor` wires real APIs into the existing tick loop. Scoring, LLM extraction, and bait detection move to Plan 3; learning/outreach/UI to Plan 4 (roadmap renumbered — each plan ships working software).

**Tech Stack:** adds `requests` and `python-dotenv`. Still no agent frameworks.

**Verified schemas (2026-07-11):** RentCast listing fields from the official
[property-listings schema](https://developers.rentcast.io/reference/property-listings-schema)
(`id`, `formattedAddress`, `addressLine1`, `addressLine2`, `city`, `state`,
`zipCode`, `latitude`, `longitude`, `propertyType`, `bedrooms`, `bathrooms`,
`squareFootage`, `yearBuilt`, `price`, `status`, `listedDate`, `removedDate`,
`lastSeenDate`, `daysOnMarket`, `history`). HPD Open Violations fields
verified against a live Socrata query of `csn4-vhvf` (`housenumber`,
`streetname`, `boro`, `zip`, `apartment`, `class`, `currentstatus`,
`novissueddate`, `violationid`, `buildingid`). Do not rename these.

---

## File Structure

```
src/doma/
├── snapshot.py            — Snapshot dataclass: the one shape every adapter emits
├── resolver.py            — street normalization, identity keys, canonical ids
├── diff.py                — diff_scan(state, snapshots) -> input events
├── live.py                — LiveExecutor: real APIs behind the Executor protocol
├── actions.py             — internal-action events shared by Live and Replay executors
└── adapters/
    ├── __init__.py
    ├── rentcast.py        — fetch + to_snapshot for RentCast
    ├── hpd.py             — HPD violations query + enrichment events
    └── stations.py        — MTA station index + nearest-station commute facts
tests/
├── test_snapshot.py
├── test_resolver.py
├── test_diff.py
├── test_rentcast.py
├── test_hpd.py
├── test_stations.py
├── test_live.py
└── fixtures/
    ├── rentcast_sample.json      — schema-faithful sample (replaced by real capture)
    ├── hpd_sample.json           — REAL records captured from Socrata
    └── stations_sample.json      — captured slice of the MTA stations dataset
scripts/
├── capture_rentcast.py    — one real API call -> fixture + full-response archive
└── capture_stations.py    — download + commit the station index
```

Existing-file changes: `state.py` (+relist handling), `events.py` (no new
types needed), `replay.py` (use shared `actions.py`), `__main__.py` (+`scan`,
`export-corpus` subcommands), `requirements.txt`, `.env.example` (new).

---

### Task 1: Snapshot — the canonical adapter output

**Files:**
- Create: `src/doma/snapshot.py`
- Test: `tests/test_snapshot.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_snapshot.py`:
```python
import pytest

from doma.snapshot import Snapshot


def _snap(**overrides) -> Snapshot:
    base = dict(source="rentcast", source_id="rc-1",
                address_line1="1208 Clay Ave", unit="4N",
                neighborhood="10456", price=2400, beds=2, baths=1.0,
                sqft=850, url=None, fee=None, days_on_market=12,
                listed_date="2026-07-01T00:00:00+00:00")
    base.update(overrides)
    return Snapshot(**base)


def test_snapshot_holds_fields() -> None:
    s = _snap()
    assert s.source == "rentcast"
    assert s.unit == "4N"
    assert s.fee is None  # unknown stays None, never defaulted


def test_snapshot_requires_source_and_address() -> None:
    with pytest.raises(ValueError, match="source"):
        _snap(source="")
    with pytest.raises(ValueError, match="address_line1"):
        _snap(address_line1="")


def test_snapshot_is_immutable() -> None:
    s = _snap()
    with pytest.raises(AttributeError):
        s.price = 9999  # type: ignore[misc]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_snapshot.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'doma.snapshot'`

- [ ] **Step 3: Implement `snapshot.py`**

`src/doma/snapshot.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_snapshot.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/doma/snapshot.py tests/test_snapshot.py
git commit -m "feat(snapshot): canonical adapter output shape with None-honesty"
```

---

### Task 2: Resolver — street normalization and identity keys

**Files:**
- Create: `src/doma/resolver.py`
- Test: `tests/test_resolver.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_resolver.py` (`canonical_id` itself is exercised in Task 4's
differ tests, where real Snapshots exist):
```python
from doma.resolver import identity_key, normalize_street


def test_normalize_street_expands_abbreviations() -> None:
    assert normalize_street("1208 Clay Ave") == "1208 clay avenue"
    assert normalize_street("240 E 10th St") == "240 east 10th street"
    assert normalize_street("55 N. 5th Blvd.") == "55 north 5th boulevard"


def test_normalize_street_collapses_noise() -> None:
    assert normalize_street("  1208   CLAY  AVENUE ") == "1208 clay avenue"
    assert normalize_street("1208 Clay Ave,") == "1208 clay avenue"


def test_identity_key_same_unit_same_key() -> None:
    a = identity_key("1208 Clay Ave", "4N")
    b = identity_key("1208 CLAY AVENUE", "4n")
    assert a == b == "1208-clay-avenue::4n"


def test_identity_key_strips_unit_prefixes() -> None:
    # RentCast says "Apt 4N", StreetEasy says "#4N" — same apartment.
    a = identity_key("1208 Clay Ave", "Apt 4N")
    b = identity_key("1208 Clay Ave", "#4N")
    c = identity_key("1208 Clay Ave", "Unit 4N")
    assert a == b == c == "1208-clay-avenue::4n"


def test_identity_key_unknown_unit_uses_fallback() -> None:
    # Two unit-less listings at the same address must NOT merge.
    a = identity_key("1208 Clay Ave", None, fallback="rentcast:rc-1")
    b = identity_key("1208 Clay Ave", None, fallback="rentcast:rc-2")
    assert a != b
    assert a == "1208-clay-avenue::rentcast:rc-1"
```

Note: `canonical_id(snapshot)` is tested in Task 4's differ tests where real
Snapshots exist; drop the unused import above (write the test file WITHOUT
that import line — it is shown here only to flag that canonical_id belongs to
this module).

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_resolver.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'doma.resolver'`

- [ ] **Step 3: Implement `resolver.py`**

`src/doma/resolver.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_resolver.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/doma/resolver.py tests/test_resolver.py
git commit -m "feat(resolver): street normalization and cross-source identity keys"
```

---

### Task 3: Relist handling in the projection

**Files:**
- Modify: `src/doma/state.py`
- Test: append to `tests/test_state.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_state.py`:
```python
def test_dead_listing_reappearing_is_a_relist() -> None:
    state = project([
        _seen("2026-07-01T09:00:00+00:00", "gp-001"),
        ev("2026-07-03T09:00:00+00:00", "listing_delisted", listing_id="gp-001"),
        _seen("2026-07-20T09:00:00+00:00", "gp-001", price=3300),
    ])
    listing = state.listings["gp-001"]
    assert listing.status == "active"
    assert listing.relist_count == 1
    assert listing.price == 3300


def test_relist_is_not_novel_inventory() -> None:
    state = project([
        _seen("2026-07-01T09:00:00+00:00", "gp-001"),
        ev("2026-07-03T09:00:00+00:00", "listing_delisted", listing_id="gp-001"),
        _seen("2026-07-20T09:00:00+00:00", "gp-001"),
    ])
    # Novelty stays at first sighting; a relist must not reset saturation.
    assert state.last_novel_ts["greenpoint"] == "2026-07-01T09:00:00+00:00"


def test_fresh_listing_has_zero_relists() -> None:
    state = project([_seen("2026-07-01T09:00:00+00:00", "gp-001")])
    assert state.listings["gp-001"].relist_count == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_state.py -v`
Expected: FAIL — `AttributeError: ... no attribute 'relist_count'` (and the
relist test fails on status staying "dead")

- [ ] **Step 3: Extend `state.py`**

In `ListingState`, add one field after `last_seen_ts`:
```python
    relist_count: int = 0
```

In `project()`, replace the `listing_seen` else-branch:
```python
            else:
                existing.last_seen_ts = e.ts
```
with:
```python
            else:
                existing.last_seen_ts = e.ts
                if existing.status == "dead":
                    existing.status = "active"
                    existing.relist_count += 1
                if p.get("price") is not None:
                    existing.price = p["price"]
```

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/python -m pytest -v`
Expected: PASS (47 passed — all Plan 1 tests still green; the smoke corpus
has no relists so its assertions are unaffected)

- [ ] **Step 5: Commit**

```bash
git add src/doma/state.py tests/test_state.py
git commit -m "feat(state): dead listings reappearing count as relists, not novelty"
```

---

### Task 4: Differ — snapshots vs state → input events

**Files:**
- Create: `src/doma/diff.py`
- Test: `tests/test_diff.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_diff.py`:
```python
from doma.diff import diff_scan
from doma.resolver import canonical_id
from doma.snapshot import Snapshot
from doma.state import project

TS = "2026-07-10T09:00:00+00:00"


def _snap(source_id: str = "rc-1", address: str = "1208 Clay Ave",
          unit: str | None = "4N", price: int | None = 2400) -> Snapshot:
    return Snapshot(source="rentcast", source_id=source_id,
                    address_line1=address, unit=unit, neighborhood="10456",
                    price=price, beds=2, baths=1.0, sqft=850, url=None,
                    fee=None, days_on_market=12, listed_date=None)


def test_new_listing_emits_listing_seen_with_canonical_id() -> None:
    events = diff_scan(project([]), [_snap()], source="rentcast", ts=TS)
    assert [e.type for e in events] == ["listing_seen"]
    payload = events[0].payload
    assert payload["listing_id"] == canonical_id(_snap())
    assert payload["source"] == "rentcast"
    assert payload["source_id"] == "rc-1"
    assert payload["price"] == 2400
    assert payload["fee"] is None  # unknown survives as None


def test_price_change_emits_price_changed() -> None:
    first = diff_scan(project([]), [_snap(price=2400)], "rentcast", TS)
    state = project(first)
    events = diff_scan(state, [_snap(price=2300)], "rentcast",
                       "2026-07-11T09:00:00+00:00")
    assert [e.type for e in events] == ["price_changed"]
    assert events[0].payload["price"] == 2300


def test_unchanged_listing_emits_listing_updated() -> None:
    first = diff_scan(project([]), [_snap()], "rentcast", TS)
    state = project(first)
    events = diff_scan(state, [_snap()], "rentcast",
                       "2026-07-11T09:00:00+00:00")
    assert [e.type for e in events] == ["listing_updated"]


def test_missing_listing_emits_delisted_for_same_source_only() -> None:
    first = diff_scan(project([]), [_snap()], "rentcast", TS)
    state = project(first)
    events = diff_scan(state, [], "rentcast", "2026-07-11T09:00:00+00:00")
    assert [e.type for e in events] == ["listing_delisted"]
    # A scan from a DIFFERENT source must not delist rentcast listings.
    events2 = diff_scan(state, [], "streeteasy_email",
                        "2026-07-11T09:00:00+00:00")
    assert events2 == []


def test_same_unit_from_two_sources_is_one_listing() -> None:
    rc = _snap()
    se = Snapshot(source="streeteasy_email", source_id="se-9",
                  address_line1="1208 CLAY AVENUE", unit="4n",
                  neighborhood="10456", price=2400, beds=2, baths=1.0,
                  sqft=None, url="https://streeteasy.com/x", fee=False,
                  days_on_market=None, listed_date=None)
    state = project(diff_scan(project([]), [rc], "rentcast", TS))
    events = diff_scan(state, [se], "streeteasy_email",
                       "2026-07-11T09:00:00+00:00")
    # Same canonical id -> a sighting, not a new listing.
    assert [e.type for e in events] == ["listing_updated"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_diff.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'doma.diff'`

- [ ] **Step 3: Implement `diff.py`**

`src/doma/diff.py`:
```python
"""Pure differ: one source's scan snapshot vs projected state -> input events.

This is where live mode manufactures the same event stream that replay
corpora record. Delisting is scoped to the scanned source: a source can only
retract listings it reported itself.
"""
from __future__ import annotations

from doma.events import Event
from doma.resolver import canonical_id
from doma.snapshot import Snapshot
from doma.state import HuntState


def _seen_payload(lid: str, snap: Snapshot) -> dict:
    return {
        "listing_id": lid, "source": snap.source, "source_id": snap.source_id,
        "address": snap.address_line1, "unit": snap.unit,
        "neighborhood": snap.neighborhood, "price": snap.price,
        "beds": snap.beds, "baths": snap.baths, "sqft": snap.sqft,
        "url": snap.url, "fee": snap.fee,
        "days_on_market": snap.days_on_market,
        "listed_date": snap.listed_date,
    }


def diff_scan(state: HuntState, snapshots: list[Snapshot], source: str,
              ts: str) -> list[Event]:
    """Compare a full scan snapshot from one source against current state."""
    events: list[Event] = []
    seen_ids: set[str] = set()
    for snap in snapshots:
        lid = canonical_id(snap)
        seen_ids.add(lid)
        known = state.listings.get(lid)
        if known is None or known.status == "dead":
            # New listing — or a dead one returning (projection counts relist).
            events.append(Event(ts=ts, type="listing_seen",
                                payload=_seen_payload(lid, snap)))
        elif snap.price is not None and snap.price != known.price:
            events.append(Event(ts=ts, type="price_changed",
                                payload={"listing_id": lid,
                                         "price": snap.price}))
        else:
            events.append(Event(ts=ts, type="listing_updated",
                                payload={"listing_id": lid,
                                         "price": snap.price}))
    for lid, listing in state.listings.items():
        if (listing.source == source and listing.status == "active"
                and lid not in seen_ids):
            events.append(Event(ts=ts, type="listing_delisted",
                                payload={"listing_id": lid}))
    return events
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_diff.py -v`
Expected: PASS (5 passed). Then full suite: `.venv/bin/python -m pytest -q` —
no regressions.

- [ ] **Step 5: Commit**

```bash
git add src/doma/diff.py tests/test_diff.py
git commit -m "feat(diff): snapshot differ emits input events with source-scoped delisting"
```

---

### Task 5: RentCast adapter

**Files:**
- Create: `src/doma/adapters/__init__.py` (empty with docstring)
- Create: `src/doma/adapters/rentcast.py`
- Create: `tests/fixtures/rentcast_sample.json`
- Create: `scripts/capture_rentcast.py`
- Modify: `requirements.txt` (+`requests`, `python-dotenv`)
- Create: `.env.example`
- Test: `tests/test_rentcast.py`

- [ ] **Step 1: Create the fixture**

`tests/fixtures/rentcast_sample.json` — schema-faithful to the documented
[property-listings schema](https://developers.rentcast.io/reference/property-listings-schema);
**labeled synthetic** until `scripts/capture_rentcast.py` replaces it with a
real capture (TDD.md fixture policy):
```json
{
  "_fixture_note": "SYNTHETIC but schema-faithful to developers.rentcast.io/reference/property-listings-schema (verified 2026-07-11). Replace with real capture via scripts/capture_rentcast.py before relying on optional-field shapes.",
  "listings": [
    {
      "id": "1208-Clay-Ave,-Apt-4N,-Bronx,-NY-10456",
      "formattedAddress": "1208 Clay Ave, Apt 4N, Bronx, NY 10456",
      "addressLine1": "1208 Clay Ave",
      "addressLine2": "Apt 4N",
      "city": "Bronx",
      "state": "NY",
      "zipCode": "10456",
      "latitude": 40.8302,
      "longitude": -73.9042,
      "propertyType": "Apartment",
      "bedrooms": 2,
      "bathrooms": 1,
      "squareFootage": 850,
      "yearBuilt": 1931,
      "status": "Active",
      "price": 2400,
      "listedDate": "2026-06-28T00:00:00.000Z",
      "removedDate": null,
      "lastSeenDate": "2026-07-10T00:00:00.000Z",
      "daysOnMarket": 12
    },
    {
      "id": "55-Nassau-Ave,-Brooklyn,-NY-11222",
      "formattedAddress": "55 Nassau Ave, Brooklyn, NY 11222",
      "addressLine1": "55 Nassau Ave",
      "addressLine2": null,
      "city": "Brooklyn",
      "state": "NY",
      "zipCode": "11222",
      "latitude": 40.7237,
      "longitude": -73.9509,
      "propertyType": "Apartment",
      "bedrooms": 1,
      "bathrooms": 1,
      "squareFootage": null,
      "status": "Active",
      "price": 3100,
      "listedDate": "2026-07-05T00:00:00.000Z",
      "removedDate": null,
      "lastSeenDate": "2026-07-10T00:00:00.000Z",
      "daysOnMarket": 5
    }
  ]
}
```

- [ ] **Step 2: Write the failing tests**

`tests/test_rentcast.py`:
```python
import json
from pathlib import Path

import pytest

from doma.adapters.rentcast import to_snapshot

FIXTURE = Path(__file__).parent / "fixtures" / "rentcast_sample.json"


def _raw(index: int) -> dict:
    return json.loads(FIXTURE.read_text())["listings"][index]


def test_to_snapshot_maps_documented_fields() -> None:
    snap = to_snapshot(_raw(0))
    assert snap.source == "rentcast"
    assert snap.source_id == "1208-Clay-Ave,-Apt-4N,-Bronx,-NY-10456"
    assert snap.address_line1 == "1208 Clay Ave"
    assert snap.unit == "Apt 4N"
    assert snap.neighborhood == "10456"  # zip is the v1 neighborhood proxy
    assert snap.price == 2400
    assert snap.beds == 2
    assert snap.days_on_market == 12


def test_to_snapshot_missing_fields_stay_none() -> None:
    snap = to_snapshot(_raw(1))
    assert snap.unit is None
    assert snap.sqft is None
    assert snap.fee is None  # RentCast has no fee field; never fabricate


def test_to_snapshot_missing_required_field_raises() -> None:
    broken = _raw(0)
    del broken["addressLine1"]
    with pytest.raises(ValueError, match="addressLine1"):
        to_snapshot(broken)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_rentcast.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'doma.adapters'`

- [ ] **Step 4: Implement the adapter**

`src/doma/adapters/__init__.py`:
```python
"""Source adapters: each normalizes one external source into Snapshots."""
```

`src/doma/adapters/rentcast.py`:
```python
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
```

`scripts/capture_rentcast.py`:
```python
"""Capture ONE real RentCast response as the test fixture (costs 1 API call).

Usage: RENTCAST_API_KEY=... .venv/bin/python scripts/capture_rentcast.py Brooklyn NY
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from doma.adapters.rentcast import fetch_listings

FIXTURE = Path(__file__).parent.parent / "tests" / "fixtures" / "rentcast_sample.json"


def main() -> None:
    api_key = os.environ.get("RENTCAST_API_KEY", "")
    if not api_key:
        sys.exit("RENTCAST_API_KEY not set")
    city, state = sys.argv[1], sys.argv[2]
    listings = fetch_listings(api_key, city, state, limit=10)
    FIXTURE.write_text(json.dumps(
        {"_fixture_note": f"REAL capture: {city}, {state} (10 listings)",
         "listings": listings}, indent=2))
    print(f"wrote {len(listings)} listings to {FIXTURE}")


if __name__ == "__main__":
    main()
```

`requirements.txt` becomes:
```
pytest
requests
python-dotenv
```

`.env.example`:
```
# RentCast API key — https://app.rentcast.io/app/api  (free tier: 50 calls/mo)
RENTCAST_API_KEY=
```

Run `.venv/bin/pip install -r requirements.txt`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_rentcast.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add src/doma/adapters tests/test_rentcast.py tests/fixtures/rentcast_sample.json scripts/capture_rentcast.py requirements.txt .env.example
git commit -m "feat(rentcast): adapter with documented-schema mapping and capture script"
```

- [ ] **Step 7 (when Luba has a key): capture the real fixture**

Run: `RENTCAST_API_KEY=... .venv/bin/python scripts/capture_rentcast.py Brooklyn NY`
Then re-run `.venv/bin/python -m pytest tests/test_rentcast.py -v`. If any
test fails on a real-payload difference, fix `to_snapshot` (not the fixture)
and commit `fix(rentcast): align mapping with captured payload`.

---

### Task 6: HPD violations enricher

**Files:**
- Create: `src/doma/adapters/hpd.py`
- Create: `tests/fixtures/hpd_sample.json`
- Test: `tests/test_hpd.py`

- [ ] **Step 1: Capture a REAL fixture (free, no key)**

Run:
```bash
curl -s "https://data.cityofnewyork.us/resource/csn4-vhvf.json?\$limit=5&boro=BROOKLYN" \
  -o tests/fixtures/hpd_sample.json
.venv/bin/python -m json.tool tests/fixtures/hpd_sample.json | head -20
```
Confirm the records contain `housenumber`, `streetname`, `boro`, `class`,
`currentstatus` (verified present 2026-07-11).

- [ ] **Step 2: Write the failing tests**

`tests/test_hpd.py`:
```python
import json
from pathlib import Path

from doma.adapters.hpd import summarize, to_enrichment_event

FIXTURE = Path(__file__).parent / "fixtures" / "hpd_sample.json"


def _records() -> list[dict]:
    return json.loads(FIXTURE.read_text())


def test_summarize_counts_by_class() -> None:
    summary = summarize(_records())
    assert set(summary) == {"class_a", "class_b", "class_c", "total"}
    assert summary["total"] == len(_records())
    assert (summary["class_a"] + summary["class_b"]
            + summary["class_c"]) <= summary["total"]


def test_summarize_empty_is_zero_not_none() -> None:
    # Zero violations is a real, known fact — distinct from "not enriched".
    assert summarize([]) == {"class_a": 0, "class_b": 0, "class_c": 0,
                             "total": 0}


def test_enrichment_event_shape() -> None:
    event = to_enrichment_event("1208-clay-avenue::4n", summarize(_records()),
                                ts="2026-07-10T09:00:00+00:00")
    assert event.type == "enrichment_added"
    assert event.payload["listing_id"] == "1208-clay-avenue::4n"
    assert event.payload["kind"] == "hpd_violations"
    assert "class_c" in event.payload
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_hpd.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'doma.adapters.hpd'`

- [ ] **Step 4: Implement `hpd.py`**

`src/doma/adapters/hpd.py`:
```python
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


def summarize(violations: list[dict]) -> dict[str, int]:
    """Count open violations by hazard class (A/B/C). Zero is a real fact."""
    counts = {"class_a": 0, "class_b": 0, "class_c": 0}
    for v in violations:
        key = f"class_{v.get('class', '').lower()}"
        if key in counts:
            counts[key] += 1
    return {**counts, "total": len(violations)}


def to_enrichment_event(listing_id: str, summary: dict[str, int],
                        ts: str) -> Event:
    """Wrap a violation summary as an enrichment_added input event."""
    return Event(ts=ts, type="enrichment_added",
                 payload={"listing_id": listing_id,
                          "kind": "hpd_violations", **summary})
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_hpd.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add src/doma/adapters/hpd.py tests/test_hpd.py tests/fixtures/hpd_sample.json
git commit -m "feat(hpd): building-health enricher over verified Socrata fields"
```

---

### Task 7: Station index + commute facts

**Files:**
- Create: `src/doma/adapters/stations.py`
- Create: `scripts/capture_stations.py`
- Create: `tests/fixtures/stations_sample.json`
- Test: `tests/test_stations.py`

- [ ] **Step 1: Verify the dataset BEFORE coding (do not trust this plan)**

The MTA subway-stations dataset is expected at data.ny.gov (dataset id
`39hk-dx4f`) with fields like `stop_name`, `daytime_routes`, `gtfs_latitude`,
`gtfs_longitude`, `borough` — **this was NOT verified when this plan was
written** (domain blocked). Verify first:
```bash
curl -s "https://data.ny.gov/resource/39hk-dx4f.json?\$limit=2" | .venv/bin/python -m json.tool
```
If the id or field names differ, find the current "MTA Subway Stations"
dataset on data.ny.gov, use ITS field names everywhere below, and note the
correction in the commit message. Then capture the fixture:
```bash
curl -s "https://data.ny.gov/resource/39hk-dx4f.json?\$limit=1000" -o tests/fixtures/stations_sample.json
```

- [ ] **Step 2: Write the failing tests**

`tests/test_stations.py` (adjust field names ONLY if Step 1 found different
ones):
```python
import json
from pathlib import Path

from doma.adapters.stations import Station, load_stations, nearest_station

FIXTURE = Path(__file__).parent / "fixtures" / "stations_sample.json"


def test_load_stations_parses_fixture() -> None:
    stations = load_stations(FIXTURE)
    assert len(stations) > 100
    first = stations[0]
    assert isinstance(first, Station)
    assert first.lat != 0.0 and first.lon != 0.0
    assert isinstance(first.routes, frozenset)


def test_nearest_station_finds_closest() -> None:
    stations = [
        Station(name="Near", routes=frozenset({"G"}), lat=40.7240, lon=-73.9510),
        Station(name="Far", routes=frozenset({"G"}), lat=40.8000, lon=-73.9000),
    ]
    station, meters = nearest_station(40.7237, -73.9509, stations)
    assert station.name == "Near"
    assert meters < 100


def test_nearest_station_filters_by_route() -> None:
    stations = [
        Station(name="G stop", routes=frozenset({"G"}), lat=40.7240, lon=-73.9510),
        Station(name="L stop", routes=frozenset({"L"}), lat=40.7100, lon=-73.9400),
    ]
    station, _ = nearest_station(40.7237, -73.9509, stations,
                                 routes=frozenset({"L"}))
    assert station.name == "L stop"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_stations.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement `stations.py`**

`src/doma/adapters/stations.py`:
```python
"""MTA station index: nearest-station walk distance for commute facts.

Stations come from a committed capture of the data.ny.gov subway-stations
dataset (see scripts/capture_stations.py) — static data, refreshed manually.
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
    """Load the captured station dataset. Field names verified at capture."""
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
```

`scripts/capture_stations.py`:
```python
"""Refresh the committed MTA station dataset capture."""
from __future__ import annotations

from pathlib import Path

import requests

URL = "https://data.ny.gov/resource/39hk-dx4f.json?$limit=1000"
FIXTURE = Path(__file__).parent.parent / "tests" / "fixtures" / "stations_sample.json"


def main() -> None:
    response = requests.get(URL, timeout=30)
    response.raise_for_status()
    FIXTURE.write_text(response.text)
    print(f"wrote {len(response.json())} stations to {FIXTURE}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_stations.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add src/doma/adapters/stations.py scripts/capture_stations.py tests/test_stations.py tests/fixtures/stations_sample.json
git commit -m "feat(stations): MTA station index with nearest-station walk distance"
```

---

### Task 8: Shared internal actions + LiveExecutor

**Files:**
- Create: `src/doma/actions.py`
- Modify: `src/doma/replay.py` (use the shared helper)
- Create: `src/doma/live.py`
- Test: `tests/test_live.py`

- [ ] **Step 1: Extract the shared internal-action helper (refactor, tests exist)**

`src/doma/actions.py`:
```python
"""Events produced by internal actions — identical in live and replay mode."""
from __future__ import annotations

from doma.events import Event
from doma.policy import Action


def scan_bookkeeping(now_iso: str) -> list[Event]:
    """Budget + completion events appended after every RentCast scan."""
    return [
        Event(ts=now_iso, type="budget_spent",
              payload={"resource": "rentcast_scan"}),
        Event(ts=now_iso, type="scan_completed",
              payload={"source": "rentcast"}),
    ]


def saturation_event(action: Action, now_iso: str) -> Event:
    """The neighborhood_saturated event for a mark_saturated action."""
    return Event(ts=now_iso, type="neighborhood_saturated",
                 payload={"neighborhood": action.target})
```

In `src/doma/replay.py`, import both helpers and replace the inline
construction of these three events inside `execute()`:
```python
from doma.actions import saturation_event, scan_bookkeeping
```
- scan branch: `return due + scan_bookkeeping(now_iso)`
- mark_saturated branch: `return [saturation_event(action, now_iso)]`

Run: `.venv/bin/python -m pytest -q` — all tests must stay green (pure
refactor; behavior identical).

Commit: `git commit -am "refactor(actions): share internal-action events between executors"`

- [ ] **Step 2: Write the failing LiveExecutor tests**

`tests/test_live.py`:
```python
from datetime import datetime, timezone

from doma.clock import ReplayClock
from doma.live import LiveExecutor
from doma.policy import Action
from doma.snapshot import Snapshot
from doma.store import EventStore


def _snap() -> Snapshot:
    return Snapshot(source="rentcast", source_id="rc-1",
                    address_line1="55 Nassau Ave", unit=None,
                    neighborhood="11222", price=3100, beds=1, baths=1.0,
                    sqft=None, url=None, fee=None, days_on_market=5,
                    listed_date=None)


def _executor(store: EventStore, snapshots: list[Snapshot]) -> LiveExecutor:
    # fetcher is injected so tests never touch the network (TDD.md hard rule).
    return LiveExecutor(store=store,
                        fetcher=lambda: snapshots,
                        clock=ReplayClock(
                            start=datetime(2026, 7, 10, tzinfo=timezone.utc)),
                        sleep_seconds=0)


def test_scan_action_fetches_diffs_and_bookkeeps() -> None:
    store = EventStore(":memory:")
    executor = _executor(store, [_snap()])
    events = executor.execute(Action(type="scan_rentcast", target=None,
                                     reason="test"))
    assert [e.type for e in events] == ["listing_seen", "budget_spent",
                                        "scan_completed"]
    assert events[0].payload["neighborhood"] == "11222"


def test_mark_saturated_matches_replay_semantics() -> None:
    store = EventStore(":memory:")
    executor = _executor(store, [])
    events = executor.execute(Action(type="mark_saturated",
                                     target="11222", reason="test"))
    assert [e.type for e in events] == ["neighborhood_saturated"]
    assert events[0].payload == {"neighborhood": "11222"}


def test_sleep_returns_no_events() -> None:
    store = EventStore(":memory:")
    executor = _executor(store, [])
    assert executor.execute(Action(type="sleep", target=None,
                                   reason="test")) == []
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_live.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'doma.live'`

- [ ] **Step 4: Implement `live.py`**

`src/doma/live.py`:
```python
"""Live mode: the Executor that touches real APIs. Fetching is injected so
every code path stays testable without a network."""
from __future__ import annotations

import time
from typing import Callable

from doma.actions import saturation_event, scan_bookkeeping
from doma.clock import Clock
from doma.diff import diff_scan
from doma.events import Event, iso
from doma.policy import Action
from doma.snapshot import Snapshot
from doma.state import project
from doma.store import EventStore


class LiveExecutor:
    """Executes actions against the real world (or an injected fetcher)."""

    def __init__(self, store: EventStore, fetcher: Callable[[], list[Snapshot]],
                 clock: Clock, sleep_seconds: int = 300) -> None:
        self._store = store
        self._fetcher = fetcher
        self._clock = clock
        self._sleep_seconds = sleep_seconds

    def execute(self, action: Action) -> list[Event]:
        """Produce the events one action yields, hitting real sources."""
        now_iso = iso(self._clock.now())
        if action.type == "scan_rentcast":
            snapshots = self._fetcher()
            state = project(self._store.read_all())
            return (diff_scan(state, snapshots, "rentcast", now_iso)
                    + scan_bookkeeping(now_iso))
        if action.type == "mark_saturated":
            return [saturation_event(action, now_iso)]
        if action.type == "sleep":
            time.sleep(self._sleep_seconds)
            return []
        raise ValueError(f"live executor got unknown action: {action.type}")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest -q`
Expected: all tests pass, no regressions.

- [ ] **Step 6: Commit**

```bash
git add src/doma/live.py tests/test_live.py
git commit -m "feat(live): LiveExecutor with injected fetcher and real diffing"
```

---

### Task 9: CLI — `doma scan` and `doma export-corpus`

**Files:**
- Modify: `src/doma/__main__.py`

- [ ] **Step 1: Add the subcommands**

Extend `main()` in `src/doma/__main__.py` — after the existing `replay`
subparser, add:
```python
    sc = sub.add_parser("scan", help="one live RentCast scan into the db")
    sc.add_argument("--db", default="doma.db", help="event store path")
    sc.add_argument("--city", required=True)
    sc.add_argument("--state", default="NY")

    xc = sub.add_parser("export-corpus",
                        help="dump the db's input events as a JSONL corpus")
    xc.add_argument("--db", default="doma.db")
    xc.add_argument("out", help="output corpus path")
```
and after `args = parser.parse_args()`, route by `args.command` (wrap the
existing replay body in `if args.command == "replay":`):
```python
    if args.command == "scan":
        import os

        from dotenv import load_dotenv

        from doma.adapters.rentcast import fetch_listings, to_snapshot
        from doma.clock import LiveClock
        from doma.live import LiveExecutor
        from doma.loop import run_tick

        load_dotenv()
        api_key = os.environ.get("RENTCAST_API_KEY", "")
        if not api_key:
            raise SystemExit("RENTCAST_API_KEY not set (see .env.example)")
        store = EventStore(args.db)

        def fetch() -> list:
            return [to_snapshot(r)
                    for r in fetch_listings(api_key, args.city, args.state)]

        executor = LiveExecutor(store=store, fetcher=fetch,
                                clock=LiveClock(), sleep_seconds=0)
        action, events = run_tick(store, PolicyConfig(), executor, LiveClock())
        print(f"decision: {action.type} ({action.reason})")
        print(f"{len(events)} events appended to {args.db}")
        return

    if args.command == "export-corpus":
        from doma.corpus import save_corpus
        from doma.events import INPUT_EVENT_TYPES

        store = EventStore(args.db)
        inputs = [e for e in store.read_all() if e.type in INPUT_EVENT_TYPES]
        save_corpus(inputs, args.out)
        print(f"wrote {len(inputs)} input events to {args.out}")
        return
```
Note: `run_tick` decides via the policy — if a scan is not due or the budget
is exhausted, `doma scan` prints the sleep decision and appends nothing.
That is correct behavior, not a bug: the budget is enforced everywhere.

- [ ] **Step 2: Verify by hand (no key needed for the refusal path)**

Run: `.venv/bin/python -m doma scan --city Brooklyn` with no key set.
Expected: exits with `RENTCAST_API_KEY not set (see .env.example)`.

Run: `.venv/bin/python -m doma export-corpus --db /tmp/empty.db /tmp/out.jsonl`
Expected: `wrote 0 input events to /tmp/out.jsonl`.

Run the full suite: `.venv/bin/python -m pytest -q` — no regressions.

- [ ] **Step 3: Commit**

```bash
git add src/doma/__main__.py
git commit -m "feat(cli): doma scan (live tick) and doma export-corpus (capture)"
```

---

### Task 10 (GATED — needs Luba's sample): StreetEasy alert-email parser

**Blocked until:** a real StreetEasy saved-search alert email is saved to
`tests/fixtures/streeteasy_alert_sample.html` (File > Save in the mail
client, or copy the HTML source; strip nothing yet).

- [ ] **Step 1 (Luba): capture the sample**

Create a StreetEasy saved search with email alerts on; when an alert
arrives, save its HTML body to `tests/fixtures/streeteasy_alert_sample.html`.
Sanitize ONLY personal data (your name/email in headers), not the listing
markup.

- [ ] **Step 2: Derive the selector table from the sample**

Open the sample and record, in a comment block at the top of
`src/doma/adapters/streeteasy_email.py`: the CSS selectors / DOM paths for
each listing card and, within a card, address, unit, neighborhood, price,
beds/baths, fee badge, and listing URL. **Never guess selectors — every one
must be traceable to the sample.** Add `beautifulsoup4` to requirements.txt.

- [ ] **Step 3: TDD the parser against the fixture**

Write `tests/test_streeteasy_email.py` asserting: number of listings in the
sample; exact address/price/url of the first card; `fee` mapping ("No fee"
badge -> False, absent -> None); output type is `list[Snapshot]` with
`source="streeteasy_email"` and `source_id` taken from the listing URL slug.
Then implement `parse_alert_html(html: str) -> list[Snapshot]` to green.
Follow the same failing-first cycle as every other task.

- [ ] **Step 4: Commit**

```bash
git add src/doma/adapters/streeteasy_email.py tests/test_streeteasy_email.py tests/fixtures/streeteasy_alert_sample.html requirements.txt
git commit -m "feat(streeteasy): alert-email parser derived from real sample"
```

(Gmail API live fetching is deliberately NOT in this plan — parsing works on
saved files first; the inbox wiring joins the live loop in Plan 3 when
enrichment actions are added to the policy ladder.)

---

### Task 11: Docs

- [ ] Update `STATUS.md` (state, next action = Plan 3, decision-log entries
  for: zip-as-neighborhood proxy, source-scoped delisting, relist-via-
  projection design, injected-fetcher testability rule).
- [ ] Update `README.md` roadmap (4 plans) and add `doma scan` /
  `doma export-corpus` to the Run section.
- [ ] Update `prd.md` build order to the 4-plan roadmap.
- [ ] Commit: `docs: mark Plan 2 shipped — status, roadmap, CLI docs`

---

## Done Criteria (Plan 2)

- Full suite green; every new module has failing-first tests; no network in
  any test (fetchers injected, fixtures committed).
- `doma scan --city Brooklyn` with a real key appends real listing events to
  a local db, respecting the budget stopping rule.
- `doma export-corpus` produces a JSONL corpus that `doma replay` accepts.
- Relist detection works end-to-end: delist + reappear -> `relist_count == 1`
  and no novelty reset (assertable in replay).
- Task 10 may remain open if the email sample hasn't been captured; note it
  in STATUS.md rather than blocking the merge.

## Explicitly deferred to Plan 3

- Scoring, LLM fact extraction, bait-flag events (uses `relist_count`,
  fee facts, price history), enrichment actions in the policy ladder,
  Gmail live fetching.
