"""Dashboard smoke test via Streamlit AppTest (no browser, no network)."""
import os

from streamlit.testing.v1 import AppTest

from doma.events import Event
from doma.store import EventStore


def _seed(db_path) -> None:
    store = EventStore(db_path)
    store.append(Event(ts="2026-07-10T00:00:00+00:00", type="listing_seen",
                       payload={"listing_id": "a", "source": "rentcast",
                                "neighborhood": "11222", "price": 3000,
                                "address": "55 Nassau Ave", "fee": False}))
    store.append(Event(ts="2026-07-10T01:00:00+00:00", type="score_computed",
                       payload={"listing_id": "a", "score": 0.8,
                                "confidence": 0.5,
                                "subscores": {"rent_value": 0.8,
                                              "light": None}}))


def test_dashboard_renders_seeded_listing(tmp_path) -> None:
    db = str(tmp_path / "ui.db")
    _seed(db)
    os.environ["DOMA_DB"] = db
    at = AppTest.from_file("app.py", default_timeout=15)
    at.run()
    assert not at.exception
    text = " ".join(str(md.value) for md in at.markdown)
    assert "55 Nassau Ave" in text            # the card rendered
    assert "waiting for your call" in text    # Today framing present


def test_dashboard_empty_store_message(tmp_path) -> None:
    os.environ["DOMA_DB"] = str(tmp_path / "missing.db")
    at = AppTest.from_file("app.py", default_timeout=15)
    at.run()
    assert not at.exception
    assert any("No hunt data yet" in str(block.value) for block in at.info)
