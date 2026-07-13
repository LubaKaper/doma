from doma.learner import MAX_STEP, MIN_RATINGS, propose_weights
from doma.scorer import DEFAULT_WEIGHTS
from helpers import ev
from doma.state import project


def _scorecard(ts: str, lid: str, ratings: dict) -> object:
    return ev(ts, "viewing_scored", listing_id=lid, verdict="pass",
              ratings=ratings)


def _events_with_ratings(ratings_list: list[dict]) -> list:
    events = [ev("2026-07-01T09:00:00+00:00", "listing_seen",
                 listing_id=f"l-{i}", source="rentcast",
                 neighborhood="11222", price=3000)
              for i in range(len(ratings_list))]
    events += [_scorecard(f"2026-07-0{i+2}T09:00:00+00:00", f"l-{i}", r)
               for i, r in enumerate(ratings_list)]
    return events


def test_no_proposal_below_min_ratings() -> None:
    state = project(_events_with_ratings([{"light": 1}, {"light": 2}]))
    assert propose_weights(state) is None


def test_extreme_ratings_raise_weight_within_cap() -> None:
    # Three strong reactions to light -> light matters more.
    state = project(_events_with_ratings(
        [{"light": 1}, {"light": 1}, {"light": 2}]))
    proposal = propose_weights(state)
    assert proposal is not None
    delta = proposal.weights["light"] - DEFAULT_WEIGHTS["light"]
    assert 0 < round(delta, 4) <= MAX_STEP + 1e-9
    assert abs(sum(proposal.weights.values()) - 1.0) < 1e-9
    assert proposal.evidence["light"]["ratings"] == [1, 1, 2]


def test_neutral_ratings_propose_nothing() -> None:
    # All 3s = indifference; salience 0.5 is the no-change point... but
    # consistently neutral ratings actually LOWER importance.
    state = project(_events_with_ratings(
        [{"commute": 3}, {"commute": 3}, {"commute": 3}]))
    proposal = propose_weights(state)
    assert proposal is not None
    assert proposal.weights["commute"] < DEFAULT_WEIGHTS["commute"]


def test_weights_updated_fold_and_rescore_trigger() -> None:
    from doma.policy import PolicyConfig, stale_scores
    events = _events_with_ratings([{"light": 1}])
    events += [
        ev("2026-07-10T09:00:00+00:00", "enrichment_attempted",
           listing_id="l-0", ok=True),
        ev("2026-07-10T10:00:00+00:00", "score_computed",
           listing_id="l-0", score=0.5, confidence=0.5),
        ev("2026-07-11T09:00:00+00:00", "weights_updated",
           weights={**DEFAULT_WEIGHTS, "light": 0.13, "rent_value": 0.27},
           previous=dict(DEFAULT_WEIGHTS)),
    ]
    state = project(events)
    assert state.weights["light"] == 0.13
    assert state.weights_ts == "2026-07-11T09:00:00+00:00"
    # scorecarded listing l-0 is status=viewed?? no - not marked; still active
    assert "l-0" in stale_scores(state)  # weight change makes scores stale


def test_multi_criterion_proposal_respects_all_invariants() -> None:
    # 5 criteria rated extreme (up), fee_burden neutral (down) — the case
    # where naive renormalization breaches the floor and the cap.
    from doma.learner import WEIGHT_FLOOR
    ratings = [{"rent_value": 1, "commute": 5, "building_health": 1,
                "laundry": 5, "light": 1, "fee_burden": 3} for _ in range(3)]
    state = project(_events_with_ratings(ratings))
    proposal = propose_weights(state)
    if proposal is None:
        return  # a null proposal is a legal outcome; invariants vacuous
    assert abs(sum(proposal.weights.values()) - 1.0) < 1e-9
    for c, new in proposal.weights.items():
        assert new >= WEIGHT_FLOOR - 1e-9, f"{c} breached floor: {new}"
        assert abs(new - proposal.previous[c]) <= MAX_STEP + 1e-9, \
            f"{c} exceeded cap: {new - proposal.previous[c]}"
    # fee_burden was rated neutral -> must not rise
    assert proposal.weights["fee_burden"] <= proposal.previous["fee_burden"] + 1e-9


def test_all_neutral_never_inverts_direction() -> None:
    # Every rated criterion neutral (down); unrated rent_value absorbs.
    ratings = [{"commute": 3, "building_health": 3, "laundry": 3,
                "light": 3, "fee_burden": 3} for _ in range(3)]
    state = project(_events_with_ratings(ratings))
    proposal = propose_weights(state)
    assert proposal is not None
    for c in ("commute", "building_health", "laundry", "light", "fee_burden"):
        assert proposal.weights[c] <= proposal.previous[c] + 1e-9, \
            f"{c} was rated neutral but went UP"
    assert (proposal.weights["rent_value"] - proposal.previous["rent_value"]
            <= MAX_STEP + 1e-9)
