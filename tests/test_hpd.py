import json
from pathlib import Path

from doma.adapters.hpd import summarize, to_enrichment_event

FIXTURE = Path(__file__).parent / "fixtures" / "hpd_sample.json"


def _records() -> list[dict]:
    return json.loads(FIXTURE.read_text())


def test_summarize_counts_by_class() -> None:
    summary = summarize(_records())
    assert set(summary) == {"class_a", "class_b", "class_c", "total", "matched"}
    assert summary["total"] == len(_records())
    assert (summary["class_a"] + summary["class_b"]
            + summary["class_c"]) <= summary["total"]


def test_summarize_empty_is_zero_but_unmatched() -> None:
    # An empty result can't prove the building is clean — it may be an
    # address-format miss, so it carries matched=False (scored as unknown).
    assert summarize([]) == {"class_a": 0, "class_b": 0, "class_c": 0,
                             "total": 0, "matched": False}


def test_enrichment_event_shape() -> None:
    event = to_enrichment_event("1208-clay-avenue::4n", summarize(_records()),
                                ts="2026-07-10T09:00:00+00:00")
    assert event.type == "enrichment_added"
    assert event.payload["listing_id"] == "1208-clay-avenue::4n"
    assert event.payload["kind"] == "hpd_violations"
    assert "class_c" in event.payload


def test_borough_from_zip() -> None:
    from doma.adapters.hpd import borough_from_zip
    assert borough_from_zip("11222") == "BROOKLYN"
    assert borough_from_zip("10456") == "BRONX"
    assert borough_from_zip("90210") is None


def test_empty_result_is_unmatched_not_clean() -> None:
    from doma.scorer import subscore_building_health
    empty = summarize([])
    assert empty["matched"] is False
    assert subscore_building_health(empty) is None
    real = summarize(_records())
    assert real["matched"] is True
    assert subscore_building_health(real) is not None
