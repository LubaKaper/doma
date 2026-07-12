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
