import pytest

from doma.decisions import mark_listing_event, scorecard_event


def test_mark_listing_event_shape() -> None:
    e = mark_listing_event("gp-001", "rejected", ts="2026-07-14T09:00:00+00:00")
    assert e.type == "listing_marked"
    assert e.payload == {"listing_id": "gp-001", "status": "rejected"}


def test_mark_listing_rejects_unknown_status() -> None:
    with pytest.raises(ValueError, match="status"):
        mark_listing_event("gp-001", "meh", ts="2026-07-14T09:00:00+00:00")


def test_scorecard_event_validates_ratings() -> None:
    e = scorecard_event("gp-001", verdict="pursue",
                        ratings={"light": 4, "commute": 2},
                        ts="2026-07-14T09:00:00+00:00")
    assert e.type == "viewing_scored"
    assert e.payload["verdict"] == "pursue"
    assert e.payload["ratings"] == {"light": 4, "commute": 2}
    with pytest.raises(ValueError, match="1..5"):
        scorecard_event("gp-001", "pass", {"light": 9},
                        ts="2026-07-14T09:00:00+00:00")
    with pytest.raises(ValueError, match="criterion"):
        scorecard_event("gp-001", "pass", {"vibes": 3},
                        ts="2026-07-14T09:00:00+00:00")
    with pytest.raises(ValueError, match="verdict"):
        scorecard_event("gp-001", "maybe", {"light": 3},
                        ts="2026-07-14T09:00:00+00:00")
