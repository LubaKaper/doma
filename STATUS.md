# STATUS.md — Where things stand

> Update this file after every substantial change (see AGENTS.md §Docs
> contract). A fresh session starts by reading this.

**Last updated:** 2026-07-13 (email parser shipped from real sample; second source live)

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

1. ~~Email parser~~ ✅ shipped 2026-07-13 from a real captured alert
   (selectors derived, never guessed; fixture sanitized; .eml gitignored).
   `doma ingest-email <file.eml>` feeds alerts into the db (incremental —
   never delists). NOTE (corrected): the alert bundles MULTIPLE saved searches — subject
   named only the NJ one. Actual content: 7 NJ + 7 NYC (5 Mott Haven,
   2 Flatbush). Gap: email listings carry neighborhood NAMES not zips, so
   zip-keyed enrichment (HPD boro, stations) skips them — needs address
   geocoding or a listing-page lookup to close. Remaining from this thread: LLM fact extraction over email
   text + outreach drafter (needs OPENROUTER_API_KEY), Gmail API auto-fetch.
2. **Calibration status:** too-good-to-be-true rule ✅, HPD matched-flag
   honesty (incl. legacy payloads) ✅, RentCast history ingestion with 90-day
   relist window ✅, tie-breaking ✅. Remaining backlog:
   - lat/lon + history backfill for pre-Plan-3 listings (they update only on
     relist; a one-off backfill scan-merge script would fix immediately).
   - listing_updated fires every scan -> full rescore each scan (harmless,
     wasteful; review finding #6).
   - Replay enrich_batch can drop later-ts enrichment events (review #7).
   - The next real `doma run` will rescore everything under the new rules
     (scan bumps activity) — expect the $900 outliers to drop/flag.
3. **Plan 4c — outreach drafter** (needs OPENROUTER_API_KEY + email facts)
   and the golden demo corpus. Learner design (approved defaults 2026-07-13):
   salience signal, ±3pt caps, ≥3 ratings gate, approval-only application. (RentCast key is live: real fixture
captured 2026-07-13, first real scan appended 502 events to local `doma.db`,
2/50 monthly calls used. `doma.db` is local-only, gitignored.)

## Plan progress

| Plan | Scope | Status |
|---|---|---|
| 1 — Core loop | events, store, corpus, projection, policy + stopping rules, clocks, tick loop, replay, smoke corpus, CLI | ✅ Shipped (44 tests) |
| 2 — Ingestion | snapshot, resolver + relist, differ, RentCast/HPD/stations adapters, LiveExecutor, scan/export CLI | ✅ Shipped (73 tests, real fixtures) — only Task 10 email parser gated on an alert-email sample |
| 3 — Scoring & bait | scorer + confidence, bait rules (relist, laddering), enrich/score policy ladder, doma run/rank CLI | ✅ Shipped (96 tests; ran on 500 real listings). LLM extraction deferred to email milestone |
| 4a — Dashboard | Streamlit UI: ranked view + why-this-score bars, filters, KPI row, decisions (reject/pursue/viewed), scorecard capture | ✅ Shipped (104 tests incl. AppTest) |
| 4b — Learner | ✅ Shipped (salience-based proposals, dashboard approval, rescore-on-update; 108 tests) |  |
| 4c — Outreach + demo | LLM drafter (needs key + email facts), golden corpus | Not written |

## Review status (full codebase, 2026-07-13)

Independent opus review over b3a3864..HEAD: verdict "with fixes" — two
confirmed learner-math bugs (floor breach, cap/direction violation via
renormalization), saturation not gating scans, SQLite locking risk. All four
fixed with invariant tests (zero-sum rebalance; saturation gate +
de-saturation; WAL+busy_timeout) plus minors (defensive scorer weights,
validated weights_updated constructor, XSS guard comment). Remaining minor
findings tracked in the backlog above.

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

## Environment quirk (Luba's machine)

Homebrew Python 3.12.13 ignores pip's underscore-prefixed editable `.pth`
(`__editable__.doma-0.1.0.pth`), so `import doma` fails after a normal
`pip install -e .`. Fix applied: a copy named
`.venv/lib/python3.12/site-packages/doma-src.pth`. If the venv is ever
recreated, re-run `pip install -e .` and re-copy the pth under a
non-underscore name (or set `PYTHONPATH=src`).

## Session continuity notes

- User handles PRs/pushes manually — never create PRs.
- User wants zero permission prompts and uninterrupted runs; project
  `.claude/settings.json` allowlists the common commands.
- Update the docs listed in AGENTS.md §Docs contract after every substantial
  change; that contract exists so no session needs re-explanation.
