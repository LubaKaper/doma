# STATUS.md — Where things stand

> Update this file after every substantial change (see AGENTS.md §Docs
> contract). A fresh session starts by reading this.

**Last updated:** 2026-07-11 (Plan 1 shipped)

## Current state

- ✅ Design spec approved and committed:
  `docs/superpowers/specs/2026-07-11-apartment-hunt-agent-design.md`
- ✅ **Plan 1 (core loop) fully implemented — all 11 tasks, 44 tests green.**
  Event model, SQLite event store, JSONL corpora, state projection, policy
  engine with stopping rules (terminal states, monthly budget cap,
  neighborhood saturation), Live/Replay clocks, tick loop, replay executor +
  driver, smoke corpus with end-to-end assertions, `python -m doma replay` CLI.
- ✅ Verified end-to-end: CLI replay of the smoke corpus produces 74 ticks,
  17 decisions; williamsburg saturates before greenpoint; budget respected;
  two replays produce identical action logs (asserted in tests).
- Venv uses Python 3.12 (`/opt/homebrew/bin/python3.12`); package installed
  editable (`pip install -e .`) so `python -m doma` works outside pytest.

## Next action

Execute **Plan 2 — Ingestion** (`docs/superpowers/plans/2026-07-11-doma-ingestion.md`):
snapshot schema, resolver + relist projection, differ, RentCast/HPD/stations
adapters, LiveExecutor, `doma scan` + `doma export-corpus` CLI. Task 10
(StreetEasy email parser) stays gated until Luba captures a real alert email
to `tests/fixtures/streeteasy_alert_sample.html`.

## Plan progress

| Plan | Scope | Status |
|---|---|---|
| 1 — Core loop | events, store, corpus, projection, policy + stopping rules, clocks, tick loop, replay, smoke corpus, CLI | ✅ Shipped (44 tests) |
| 2 — Ingestion | snapshot, resolver + relist, differ, RentCast/HPD/stations adapters, LiveExecutor, scan/export CLI, email parser (gated) | Plan written, not started |
| 3 — Scoring & bait | LLM fact extraction, scorer, bait detector, enrichment actions in policy ladder, Gmail live fetch | Not written |
| 4 — Learning, outreach, UI | preference learner, outreach drafter, Streamlit dashboard, golden demo corpus | Not written |

## Review status (Plan 1)

- Unit A (scaffold + events): implemented by subagent, independently
  spec-reviewed (✅ compliant) and quality-reviewed; the one Important finding
  (`iso()` must reject naive datetimes — replay-determinism risk) was fixed
  with a test (`fa96e96`).
- Units B–E: executed inline, transcribed from the reviewed plan (the plan
  itself contains the full code and passed a type/timing consistency review
  when written). Subagent reviews were unavailable (session limit).
  **Follow-up:** run `/code-review` over `b3a3864..HEAD` for an independent
  pass when convenient.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-11 | Dual purpose, equal weight: real hunt + portfolio demo | User choice; drives replay+live dual mode from day one |
| 2026-07-11 | ToS-clean sources only: RentCast API + StreetEasy alert-email parsing + NYC Open Data + MTA GTFS; **no scraping ever** | Live research verified: no official StreetEasy/Zillow/Craigslist APIs; RentCast free tier (50 calls/mo, 500 listings/call) fits; own-inbox parsing is established practice |
| 2026-07-11 | Architecture B: deterministic policy loop; LLM only extracts facts + drafts outreach | Makes stopping rules testable; evaluator engineering is the portfolio centerpiece |
| 2026-07-11 | Feedback = structured post-viewing scorecard (verdict + 1–5 per criterion) | Per-criterion residuals → deterministic, explainable weight updates |
| 2026-07-11 | Demo = replay mode over recorded corpus + live mode for real hunt | Reviewer runs full loop offline, zero keys, deterministic |
| 2026-07-11 | SQLite event store (not JSONL); corpora/fixtures as JSONL | Projections need ordered/filtered queries; stdlib |
| 2026-07-11 | Light scoring v1 = extractable facts only; building-shadow geometry deferred to v2 | Geometry is a separate project hiding inside this one |
| 2026-07-11 | Streamlit UI, not Vercel | Agent is a long-running Python loop + local SQLite; Vercel would need a separate JS app + API + hosted state |
| 2026-07-11 | Work split into sequential plans (now 4: core loop / ingestion / scoring & bait / learning+UI) | Each ships working, tested software on its own |
| 2026-07-11 | Project named **Doma**; package renamed hunt→doma | User choice; renamed while cheap |
| 2026-07-11 | v1 neighborhood = zip code (RentCast exposes no neighborhood); delisting is source-scoped; relists detected via canonical-id resurrection in the projection | Honest data + cross-source dedup design (Plan 2) |
| 2026-07-11 | `iso()` rejects naive datetimes | Quality review: naive datetimes silently convert via local machine time — breaks replay determinism |
| 2026-07-11 | setuptools src-layout build + editable install added | Plan omission: pytest `pythonpath` doesn't apply to plain `python -m doma`; the demo command requires an installed package |

## Open questions

- ~~Final project name~~ — named **Doma** (2026-07-11). Folder still `apartment-search`; rename is Luba's call (it would touch local settings paths).
- Luba's actual criteria weights + train line — captured via cold-start
  interview when the learner lands (Plan 3), not hardcoded.
- StreetEasy alert-email HTML structure — capture a real sample before
  writing Plan 2's parser task.
- De-saturation (novel listing in a saturated neighborhood re-opens it) —
  deliberately deferred; revisit in Plan 2 when real data flows.

## Session continuity notes

- User handles PRs/pushes manually — never create PRs.
- User wants zero permission prompts and uninterrupted runs; project
  `.claude/settings.json` allowlists the common commands.
- Update the docs listed in AGENTS.md §Docs contract after every substantial
  change; that contract exists so no session needs re-explanation.
