# PRD — NYC Apartment-Hunt Agent

**Project:** Doma · **Owner:** Luba Kaper · **Created:** 2026-07-11 · **Status:** v1 in development

## Problem

Hunting for an NYC apartment means manually re-checking multiple sites daily,
eyeballing every listing against the same personal criteria, getting burned by
relisted bait and broker-fee games, and writing the same inquiry message over
and over. The signal (a handful of genuinely good fits per week) is buried in
noise, and the hunter's own evolving taste never feeds back into the search.

## Product

An agent that runs the hunt continuously: scans ToS-clean listing sources,
scores each listing against the user's real criteria with learned weights,
flags bait with evidence, drafts inquiry messages for human approval, and
recalibrates scoring from post-viewing feedback.

**Loop:** scan → score → outreach draft → preference feedback → (re-weighted) scan.

## Dual purpose, equal weight

1. **Real tool** — live mode runs an actual hunt for the user.
2. **Portfolio piece** — replay mode demos the full loop offline,
   deterministically, with zero API keys, for a reviewer who is not
   apartment hunting.

**Engineering thesis (what the portfolio demonstrates):** every decision is a
tested function; the LLM only reads (fact extraction) and writes (drafts),
never decides. The centerpiece is loop engineering — the evaluator, the
decision policy, and the stopping rules.

## Users

- **Primary:** the author, running a real hunt.
- **Secondary:** a portfolio reviewer cloning the repo and running the demo.

## Functional requirements

### Ingestion (v1)
- Pull listings via the RentCast API (official, free tier; ≤40 calls/month
  enforced by the agent itself).
- Parse StreetEasy saved-search alert emails from the user's own inbox
  (Gmail API).
- Enrich with NYC Open Data (HPD violations, DOB complaints) and MTA GTFS
  (walk-to-station, headways).
- **Never scrape.** No StreetEasy/Zillow/Craigslist scraping, no third-party
  scraper APIs. This is a hard product decision, not a technical gap.

### Scoring (v1)
- Criteria: rent value, light, laundry, commute, building health, fee burden.
- Weighted sum with per-listing confidence from fact completeness.
- Unknown facts are `None` — never imputed, never defaulted. Missing facts
  lower confidence, not the score.
- Light scoring uses extractable facts only (floor, stated exposure, claims
  tagged as claims). Building-shadow geometry is v2.

### Bait detection (v1)
- Relist detection: same unit reappearing under new ID or reset days-on-market,
  flagged with full sighting history.
- Fee inconsistency: "no fee" claims contradicted by fee facts.
- Price-drop laddering.

### Agent loop (v1)
- Deterministic tick loop: policy function ranks candidate actions; stopping
  rules are first-class (terminal listing states, neighborhood saturation,
  monthly budget caps, outreach confidence gate).
- Replay mode: recorded input events in, decisions recomputed and assertable.

### Outreach (v1)
- LLM drafts inquiry from verified facts only.
- Nothing sends without explicit human approval; v1 stops at
  copy-to-clipboard (no sending integration at all).

### Preference learning (v1)
- Post-viewing structured scorecard: overall verdict + 1–5 per criterion.
- Per-criterion residuals drive deterministic, bounded weight updates.
- Updates applied only after the user approves a before/after diff; full
  audit history as events.

### UI (v1)
- Streamlit dashboard: ranked listings with score breakdowns, bait flags with
  evidence, pending approvals, loop activity log, budget meters.

## Non-goals (v1)

- Sending outreach automatically (drafts only)
- Building-shadow light modeling (v2)
- Any scraping or scraper-API usage (permanent)
- Hosted deployment (v2 decision)
- Sale listings, roommate matching, cities other than NYC

## Success criteria

- Replay demo runs offline, deterministically, with zero API keys.
- Every loop decision is unit-testable; stopping rules have named predicates.
- No fabricated data anywhere in the pipeline.
- No outreach leaves without human approval; no weight change without an
  approved diff.
- Live mode sustains a real hunt within the RentCast free tier.

## Build order

1. **Plan 1 — Core loop** (event store, projection, policy + stopping rules,
   replay harness, CLI). `docs/superpowers/plans/2026-07-11-core-loop.md`
2. **Plan 2 — Ingestion** (adapters, resolver + relist detection, differ,
   live executor, corpus capture). `docs/superpowers/plans/2026-07-11-doma-ingestion.md`
3. **Plan 3 — Scoring & bait** (LLM fact extraction, scorer, bait detector,
   enrichment actions in the policy ladder).
4. **Plan 4 — Learning, outreach, UI** (preference learner, outreach drafter,
   Streamlit dashboard, golden demo corpus).

Full design: `docs/superpowers/specs/2026-07-11-apartment-hunt-agent-design.md`
