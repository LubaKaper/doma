import pytest
from helpers import ev

from hunt.corpus import load_corpus, save_corpus


def test_corpus_round_trip_sorted_by_ts(tmp_path) -> None:
    path = tmp_path / "corpus.jsonl"
    events = [
        ev("2026-07-02T09:00:00+00:00", "listing_seen", listing_id="b",
           source="rentcast", neighborhood="greenpoint", price=3000),
        ev("2026-07-01T09:00:00+00:00", "listing_seen", listing_id="a",
           source="rentcast", neighborhood="greenpoint", price=2900),
    ]
    save_corpus(events, path)
    loaded = load_corpus(path)
    assert [e.payload["listing_id"] for e in loaded] == ["a", "b"]


def test_corpus_rejects_decision_events(tmp_path) -> None:
    path = tmp_path / "corpus.jsonl"
    save_corpus([ev("2026-07-01T09:00:00+00:00", "scan_completed",
                    source="rentcast")], path)
    with pytest.raises(ValueError, match="not an input event type"):
        load_corpus(path)


def test_corpus_missing_file_names_the_file(tmp_path) -> None:
    with pytest.raises(RuntimeError, match="nope.jsonl"):
        load_corpus(tmp_path / "nope.jsonl")
