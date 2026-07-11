# STATUS.md — Where things stand

> Update this file after every substantial change (see AGENTS.md §Docs
> contract). A fresh session starts by reading this.

**Last updated:** 2026-07-11

## Current state

- ✅ Design spec written, approved by Luba, committed:
  `docs/superpowers/specs/2026-07-11-apartment-hunt-agent-design.md`
- ✅ Implementation Plan 1 (core loop) written and committed:
  `docs/superpowers/plans/2026-07-11-core-loop.md` — 11 TDD tasks, all
  checkboxes unchecked (nothing executed yet).
- ✅ Doc set created: prd.md, TDD.md, AGENTS.md, CLAUDE.md, README.md, STATUS.md.
- ❌ No source code exists yet. No venv yet.

## Next action

Execute Plan 1, Task 1 (project scaffold), following the plan's steps
exactly. **Pending user decision:** execution approach — subagent-driven
(fresh subagent per task, recommended) vs. inline. Ask if not yet answered.

## Plan progress

| Plan | Scope | Status |
|---|---|---|
| 1 — Core loop | events, store, corpus, projection, policy + stopping rules, clocks, tick loop, replay, smoke corpus, CLI | Written, not started |
| 2 — Sources & scoring | RentCast/Gmail/OpenData/GTFS adapters, resolver + relist detection, scorer, bait detector, LLM fact extraction | Not written (write after Plan 1 ships) |
| 3 — Learning, outreach, UI | preference learner, outreach drafter, Streamlit dashboard, golden demo corpus | Not written |

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
| 2026-07-11 | Work split into 3 sequential plans | Each ships working, tested software on its own |

## Open questions

- Execution approach for Plan 1 (subagent-driven vs. inline) — awaiting user.
- Final project name (working: apartment-search).
- Luba's actual criteria weights + train line — captured via cold-start
  interview when the learner lands (Plan 3), not hardcoded.
- StreetEasy alert-email HTML structure — capture a real sample before
  writing Plan 2's parser task.

## Session continuity notes

- User handles PRs/pushes manually — never create PRs.
- Update the docs listed in AGENTS.md §Docs contract after every substantial
  change; that contract exists so no session needs re-explanation.
