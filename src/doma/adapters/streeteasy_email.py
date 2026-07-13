"""StreetEasy alert-email parser: the user's own inbox as a listing source.

Selector table derived from a real captured alert (2026-07-13), never
guessed:
  a.ListingCardLink                     one anchor per listing card (href =
                                        tracked click-through URL)
  .ListingCard-info--area               "Rental Unit in West Side"
  .ListingCard-info--address            "7-9 Gifford Avenue #203"
  .ListingCard-info--price              "$1,775 base rent"
  card text "N Bed"/"Studio"            beds
  card text "No Fee" (when present)     fee=False; absent -> None
"""
from __future__ import annotations

import email
import email.policy
import re
from pathlib import Path

from bs4 import BeautifulSoup

from doma.snapshot import Snapshot


def extract_html(eml_path: str | Path) -> str:
    """The text/html body of a saved .eml message."""
    p = Path(eml_path)
    try:
        msg = email.message_from_bytes(p.read_bytes(),
                                       policy=email.policy.default)
    except OSError as exc:
        raise RuntimeError(f"failed to read email {p}: {exc}") from exc
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            return part.get_content()
    raise ValueError(f"{p}: no text/html part in message")


def _slug(text: str) -> str:
    return re.sub(r"[^\w]+", "-", text.lower()).strip("-")


def parse_alert_html(html: str) -> list[Snapshot]:
    """Every listing card in an alert email as a Snapshot."""
    soup = BeautifulSoup(html, "html.parser")
    snaps: list[Snapshot] = []
    for card in soup.select("a.ListingCardLink"):
        address_el = card.select_one(".ListingCard-info--address")
        if address_el is None:
            continue
        full_address = address_el.get_text(strip=True)
        if "#" in full_address:
            address, unit = (x.strip() for x in full_address.split("#", 1))
        else:
            address, unit = full_address, None
        if not address:
            continue

        price = None
        price_el = card.select_one(".ListingCard-info--price")
        if price_el is not None:
            m = re.search(r"\$([\d,]+)", price_el.get_text())
            if m:
                price = int(m.group(1).replace(",", ""))

        neighborhood = "unknown"
        area_el = card.select_one(".ListingCard-info--area")
        if area_el is not None:
            area = area_el.get_text(strip=True)
            if " in " in area:
                neighborhood = area.split(" in ", 1)[1].strip().lower()

        text = card.get_text(" ", strip=True)
        beds = None
        bed_match = re.search(r"(\d+)\s+Bed", text)
        if bed_match:
            beds = int(bed_match.group(1))
        elif re.search(r"\bStudio\b", text):
            beds = 0
        baths = None
        bath_match = re.search(r"([\d.]+)\s+Bath", text)
        if bath_match:
            baths = float(bath_match.group(1))
        sqft = None
        sqft_match = re.search(r"([\d,]+)\s*(?:ft|sq)", text, re.I)
        if sqft_match:
            sqft = int(sqft_match.group(1).replace(",", ""))
        fee = False if re.search(r"\bNo Fee\b", text, re.I) else None

        snaps.append(Snapshot(
            source="streeteasy_email",
            source_id=_slug(full_address),
            address_line1=address,
            unit=unit,
            neighborhood=neighborhood,
            price=price,
            beds=beds,
            baths=baths,
            sqft=sqft,
            url=card.get("href"),
            fee=fee,
            days_on_market=None,
            listed_date=None,
        ))
    return snaps
