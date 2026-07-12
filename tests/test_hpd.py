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
