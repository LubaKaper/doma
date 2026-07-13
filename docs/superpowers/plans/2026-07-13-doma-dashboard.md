# Doma Dashboard Implementation Plan (Plan 4a)

> Executed inline (TDD). Learner math (4b) and outreach drafting (4c) are
> deliberately deferred: the learner design is a user-led conversation; the
> drafter needs the LLM + email-sourced facts.

**Goal:** A Streamlit dashboard over the event store: ranked listings with
score breakdowns and bait evidence, budget meters, activity log — plus the
human's decisions (reject / pursuing / viewed + post-viewing scorecard)
entering the system as events.

## Design

- **New input event `listing_marked`** `{listing_id, status}` — the user is
  an input source. Projection sets the status (validated against
  active|rejected|pursuing|viewed). Terminal listings already cost zero
  actions in the policy ladder.
- **`viewing_scored` fold** — projection stores the latest scorecard on the
  listing (`scorecard` field); the learner (4b) will consume the full event
  history, not just the latest.
- **Projection stores `subscores`** from score_computed so the UI can show
  why-this-score without recomputing.
- **`doma/decisions.py`** — pure, validated event builders
  (`mark_listing_event`, `scorecard_event`); the UI stays a thin shell.
  Criteria for scorecards = scorer weight keys.
- **`app.py`** (repo root, matching Fourth's convention): sidebar (db path
  via DOMA_DB env or text input, budget meter, saturated zips), Ranked tab
  (expanders: subscores, HPD, commute, price history, bait evidence, decision
  buttons + scorecard form), Activity tab (recent events, counts). UI writes
  ONLY via decisions.py builders + store.append.
- **Tests:** decisions builders (validation, event shapes), projection folds,
  and a Streamlit AppTest smoke test (renders against a seeded temp db).
- Adds `streamlit` to requirements.

## Done criteria
- Suite green incl. AppTest smoke; dashboard runs on the real doma.db;
  marking a listing rejected removes it from ranked view on rerun and the
  event is in the store.
