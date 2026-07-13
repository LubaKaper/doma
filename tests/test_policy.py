from datetime import datetime

from helpers import ev

from doma.policy import (Action, PolicyConfig, budget_exhausted, decide,
                         is_terminal, scan_due, stale_neighborhoods)
from doma.state import ListingState, project


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


def _listing(status: str) -> ListingState:
    return ListingState(listing_id="x", source="rentcast",
                        neighborhood="greenpoint", price=3000, status=status,
                        first_seen_ts="2026-07-01T09:00:00+00:00",
                        last_seen_ts="2026-07-01T09:00:00+00:00")


CFG = PolicyConfig()  # scan_interval_hours=24, monthly_scan_cap=40, saturation_days=7


def test_terminal_statuses() -> None:
    assert not is_terminal(_listing("active"))
    for status in ("rejected", "dead", "viewed", "pursuing"):
        assert is_terminal(_listing(status))


def test_budget_exhausted_counts_current_month_only() -> None:
    state = project([ev("2026-07-01T09:00:00+00:00", "budget_spent",
                        resource="rentcast_scan")] * 40)
    assert budget_exhausted(state, _dt("2026-07-15T00:00:00+00:00"), CFG)
    assert not budget_exhausted(state, _dt("2026-08-01T00:00:00+00:00"), CFG)


def test_scan_due_when_never_scanned() -> None:
    state = project([])
    assert scan_due(state, _dt("2026-07-01T00:00:00+00:00"), CFG)


def test_scan_not_due_within_interval() -> None:
    state = project([ev("2026-07-01T09:00:00+00:00", "scan_completed",
                        source="rentcast")])
    assert not scan_due(state, _dt("2026-07-01T20:00:00+00:00"), CFG)
    assert scan_due(state, _dt("2026-07-02T09:00:00+00:00"), CFG)


def test_stale_neighborhoods_after_saturation_window() -> None:
    state = project([
        ev("2026-07-01T09:00:00+00:00", "listing_seen", listing_id="gp-001",
           source="rentcast", neighborhood="greenpoint", price=3000),
    ])
    assert stale_neighborhoods(state, _dt("2026-07-05T09:00:00+00:00"), CFG) == []
    assert stale_neighborhoods(state, _dt("2026-07-08T09:00:00+00:00"), CFG) == ["greenpoint"]


def test_stale_skips_already_saturated() -> None:
    state = project([
        ev("2026-07-01T09:00:00+00:00", "listing_seen", listing_id="gp-001",
           source="rentcast", neighborhood="greenpoint", price=3000),
        ev("2026-07-08T10:00:00+00:00", "neighborhood_saturated",
           neighborhood="greenpoint"),
    ])
    assert stale_neighborhoods(state, _dt("2026-07-09T09:00:00+00:00"), CFG) == []


def test_decide_priority_saturation_before_scan() -> None:
    state = project([
        ev("2026-07-01T09:00:00+00:00", "listing_seen", listing_id="gp-001",
           source="rentcast", neighborhood="greenpoint", price=3000),
    ])
    action = decide(state, _dt("2026-07-09T09:00:00+00:00"), CFG)
    assert action == Action(type="mark_saturated", target="greenpoint",
                            reason="no novel inventory in 7 days")


def test_decide_scans_when_due_and_budgeted() -> None:
    action = decide(project([]), _dt("2026-07-01T00:00:00+00:00"), CFG)
    assert action.type == "scan_rentcast"


def test_decide_sleeps_when_budget_exhausted() -> None:
    state = project([ev("2026-07-01T09:00:00+00:00", "budget_spent",
                        resource="rentcast_scan")] * 40)
    action = decide(state, _dt("2026-07-15T00:00:00+00:00"), CFG)
    assert action.type == "sleep"
    assert "budget" in action.reason


def test_decide_sleeps_when_nothing_to_do() -> None:
    state = project([ev("2026-07-01T09:00:00+00:00", "scan_completed",
                        source="rentcast")])
    action = decide(state, _dt("2026-07-01T10:00:00+00:00"), CFG)
    assert action == Action(type="sleep", target=None, reason="nothing to do")


def _active_unenriched(lid: str = "e-1"):
    return ev("2026-07-01T09:00:00+00:00", "listing_seen", listing_id=lid,
              source="rentcast", neighborhood="11222", price=3000)


def test_decide_enriches_before_scoring_and_scanning() -> None:
    state = project([
        _active_unenriched(),
        ev("2026-07-01T09:00:00+00:00", "scan_completed", source="rentcast"),
    ])
    action = decide(state, _dt("2026-07-01T10:00:00+00:00"), CFG)
    assert action.type == "enrich_batch"


def test_decide_scores_after_enrichment() -> None:
    state = project([
        _active_unenriched(),
        ev("2026-07-01T09:30:00+00:00", "enrichment_attempted",
           listing_id="e-1", ok=True),
        ev("2026-07-01T09:00:00+00:00", "scan_completed", source="rentcast"),
    ])
    action = decide(state, _dt("2026-07-01T10:00:00+00:00"), CFG)
    assert action.type == "score_batch"


def test_decide_sleeps_when_scored_and_nothing_due() -> None:
    state = project([
        _active_unenriched(),
        ev("2026-07-01T09:30:00+00:00", "enrichment_attempted",
           listing_id="e-1", ok=True),
        ev("2026-07-01T09:45:00+00:00", "score_computed",
           listing_id="e-1", score=0.5, confidence=0.5),
        ev("2026-07-01T09:00:00+00:00", "scan_completed", source="rentcast"),
    ])
    action = decide(state, _dt("2026-07-01T10:00:00+00:00"), CFG)
    assert action.type == "sleep"


def test_new_activity_makes_score_stale_again() -> None:
    state = project([
        _active_unenriched(),
        ev("2026-07-01T09:30:00+00:00", "enrichment_attempted",
           listing_id="e-1", ok=True),
        ev("2026-07-01T09:45:00+00:00", "score_computed",
           listing_id="e-1", score=0.5, confidence=0.5),
        ev("2026-07-02T09:00:00+00:00", "price_changed",
           listing_id="e-1", price=2800),
        ev("2026-07-02T09:00:00+00:00", "scan_completed", source="rentcast"),
    ])
    action = decide(state, _dt("2026-07-02T10:00:00+00:00"), CFG)
    assert action.type == "score_batch"


def test_scan_skipped_when_all_known_neighborhoods_saturated() -> None:
    state = project([
        ev("2026-07-01T09:00:00+00:00", "listing_seen", listing_id="s-1",
           source="rentcast", neighborhood="11222", price=3000),
        ev("2026-07-01T09:10:00+00:00", "enrichment_attempted",
           listing_id="s-1", ok=True),
        ev("2026-07-01T09:20:00+00:00", "score_computed",
           listing_id="s-1", score=0.5, confidence=0.5),
        ev("2026-07-09T09:00:00+00:00", "neighborhood_saturated",
           neighborhood="11222"),
    ])
    action = decide(state, _dt("2026-07-10T09:00:00+00:00"), CFG)
    assert action.type == "sleep"
    assert "saturated" in action.reason
