"""Parser tests against a REAL (sanitized) StreetEasy alert email."""
from pathlib import Path

from doma.adapters.streeteasy_email import extract_html, parse_alert_html

FIXTURE = Path(__file__).parent / "fixtures" / "streeteasy_alert_sample.html"


def _snaps():
    return parse_alert_html(FIXTURE.read_text())


def test_parses_all_listing_cards() -> None:
    snaps = _snaps()
    assert len(snaps) >= 10  # subject promised 10; extra "similar" cards ok
    assert all(s.source == "streeteasy_email" for s in snaps)


def test_first_card_fields_match_real_markup() -> None:
    snap = next(s for s in _snaps() if s.address_line1 == "7-9 Gifford Avenue")
    assert snap.unit == "203"
    assert snap.price == 1775
    assert snap.beds == 1
    assert snap.neighborhood == "west side"
    assert snap.url is not None and "streeteasy.com" in snap.url
    assert snap.fee in (False, None)  # only an explicit badge sets False


def test_unknowns_stay_none() -> None:
    for snap in _snaps():
        assert snap.sqft is None or isinstance(snap.sqft, int)
        assert snap.days_on_market is None  # alerts don't carry DOM
