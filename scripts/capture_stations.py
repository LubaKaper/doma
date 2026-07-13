"""Refresh the committed MTA station dataset capture (free, no key)."""
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
