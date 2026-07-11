# Design: NYC Apartment-Hunt Agent

**Date:** 2026-07-11
**Status:** Approved pending user review
**Working name:** apartment-search (final name TBD)

## 1. Purpose

An agent that runs a continuous NYC apartment hunt: ingests listings from
ToS-clean sources, scores each against the user's real criteria with learned
weights, flags bait (relists, fee games), drafts inquiry messages for human
approval, and recalibrates its scoring from post-viewing feedback.

**Portfolio thesis:** every decision is a tested function; the LLM only reads
and writes, never decides. The centerpiece is loop engineering — the
evaluator, the decision policy, and the stopping rules.

**Dual use, equal weight:** a real tool for an actual hunt (live mode) and a
portfolio demo (replay mode). Both run the identical loop; only the event
source differs.

### Success criteria

- Replay demo runs offline with zero API keys and deterministic output.
- Every loop decision (scan, enrich, draft, stop) is unit-testable.
- No fabricated data anywhere: unknown facts are `None`, scores carry
  confidence, LLM extractions are validated against schema.
- No outreach leaves the system without explicit human approval.
- Scoring weights change only via human-approved diffs, with full audit history.

## 2. Data sources (researched 2026-07-11, verified live)

| Source | Role | Status |
|---|---|---|
| RentCast API | Daily bulk scan. Free tier 50 calls/mo; one geo-search returns up to 500 listings with active/inactive status, days-on-market, listing history. Budget ≤40 calls/mo enforced by the policy engine. | Official API, ToS-clean |
| StreetEasy saved-search email alerts | Real-time NYC-native coverage. User configures saved searches; agent parses alert emails from the user's own inbox via Gmail API. Established practice (Mailparser sells templates for it). | ToS-clean (own inbox) |
| NYC Open Data (Socrata) | Enrichment: Open HPD Violations (csn4-vhvf), DOB Complaints (eabe-havv), housing litigation. Building-health signals by address/BBL. | Open data |
| MTA GTFS | Commute scoring: walk-to-station distance + headways for the user's line. Static GTFS, refreshed occasionally. | Open data |

**Explicitly rejected:** StreetEasy/Zillow/Craigslist/Zumper/Apartments.com
scraping (no official APIs; ToS violations; Zillow public API retired 2021;
Craigslist RSS dead). Third-party scraper APIs (Apify etc.) rejected as
ToS-gray by proxy. This rejection is a README talking point.

## 3. Architecture — event-sourced tick loop

Append-only **event store** (SQLite). Event types include:
`listing_seen`, `listing_updated`, `price_changed`, `alert_email_received`,
`enrichment_added`, `facts_extracted`, `score_computed`, `bait_flagged`,
`outreach_proposed`, `outreach_approved`, `outreach_rejected`,
`viewing_scheduled`, `viewing_scored`, `weights_proposed`, `weights_updated`,
`budget_spent`, `neighborhood_saturated`.

**State** is a pure projection of events — no mutable state lives outside the
store. The dashboard and the policy engine read projections; nothing writes
state directly.

**Tick loop:** each tick, the policy engine
1. builds current state from events,
2. generates candidate actions (scan source X, enrich listing Y, extract facts
   for Z, propose outreach for W, request feedback, sleep),
3. ranks them with explicit, tested utility rules,
4. executes the top action,
5. appends resulting events.

**Live mode** feeds real time + real APIs. **Replay mode** feeds a recorded
event corpus at accelerated time. Same loop, byte-identical decisions — this
is what makes stopping rules assertable in pytest.

## 4. Components

Each component is a module with one purpose, a typed public function, and its
own test file.

### Adapters (uniform output schema)
- `rentcast_adapter` — geo-search pull, normalizes to canonical listing schema.
- `email_alert_adapter` — Gmail API, parses StreetEasy alert emails into the
  same schema. Parser is deterministic (HTML structure), LLM fallback for
  ambiguous bodies is schema-validated.
- `opendata_enricher` — HPD violations / DOB complaints by address, joined to
  listings; produces building-health facts.
- `gtfs_commute` — precomputed station index; walk distance + headway per
  listing.

### Resolver
Cross-source identity resolution (normalized address + unit) and **relist
detection**: same unit reappearing under a new listing ID or with reset
days-on-market is linked to its full sighting history and flagged.

### Scorer
`score = Σ weight_i × subscore_i`, with per-listing confidence based on fact
completeness. Criteria (v1): rent value, light, laundry, commute, building
health, fee burden.
- Subscores come only from extractable facts. Unknown = `None`, never imputed;
  missing facts lower confidence, never the score itself via guesses.
- Light (v1): floor number, stated exposure, listing-text claims tagged as
  *claims*. Building-shadow geometry from open-data footprints is **v2**.
- LLM narrow job #1: extract structured facts (floor, exposure, laundry
  location, fee terms) from listing text / email bodies; output validated
  against a strict schema; failures logged, never silently defaulted.

### Bait detector
Deterministic rules over listing history: relist churn, "no fee" claims
contradicted by fee facts, price-drop laddering. Emits `bait_flagged` events
with the evidence trail.

### Policy engine + stopping rules (the centerpiece)
- Utility-ranked candidate actions; ranking rules are pure functions with
  table-driven tests.
- **Per-listing terminal states:** `rejected`, `dead` (delisted), `viewed`,
  `pursuing`. Terminal listings cost zero future actions.
- **Neighborhood saturation:** no novel inventory in N ticks → propose widen
  or stop for that area.
- **Global budgets:** RentCast calls/month, outreach drafts/week, LLM
  calls/day — hard caps enforced before action execution.
- **Outreach confidence gate:** minimum score AND minimum fact-completeness
  before a draft is even proposed.

### Preference learner
- Post-viewing **structured scorecard**: overall verdict (pursue/pass) + 1–5
  per criterion actually experienced.
- Per-criterion residual (predicted vs experienced) drives a deterministic
  weight-update rule (bounded step size, normalized weights).
- Updates are **proposed as a before/after diff**; applied only on human
  approval; every change is a `weights_updated` event → full audit history of
  the taste model.
- Cold start: initial-weights interview.

### Outreach drafter
LLM narrow job #2: draft inquiry from verified facts only. Human approval
gate; v1 stops at copy-to-clipboard — no sending integration.

### UI
Streamlit dashboard reading SQLite projections: ranked listings with
why-this-score breakdowns, bait flags with evidence, pending approvals
(outreach drafts, weight diffs), loop activity log, budget meters.

Decision rationale: Vercel rejected — the agent is a long-running Python loop
writing local SQLite; Vercel hosts serverless JS frontends and would require a
separate Next.js app + API layer + hosted state. Streamlit reads the SQLite
file directly, keeps the repo one-language, and matches the author's prior
project (Fourth). Hosted demo, if ever, is a v2 decision.

## 5. Error handling

- Every external call (RentCast, Gmail, Socrata, OpenRouter) wrapped with
  clear per-source failure messages; a failed source degrades that tick, never
  crashes the loop.
- Missing fields are `None`, never `0`, never imputed.
- LLM outputs are schema-validated; invalid output is a logged failure event,
  not a retry-until-plausible.
- No silent except blocks.

## 6. Testing

- **Unit:** policy ranking rules, every stopping rule, scorer, learner update
  math, bait rules, adapters against fixture payloads (real captured
  responses, sanitized).
- **Replay integration (golden corpus):** a few weeks of real captured events,
  sanitized. Assertions on loop behavior: "relist flagged on day 6,"
  "saturation fires for neighborhood X on day 11," "weight diff proposed after
  scorecard 3," "RentCast budget never exceeded."
- **Property-ish checks:** weights always normalized; terminal listings never
  receive actions; confidence monotonically increases with fact count.

## 7. Demo (portfolio story)

`python -m hunt demo` — replays the golden corpus at accelerated time with the
dashboard live. A reviewer with zero API keys watches the agent scan, score,
flag a relist, gate an outreach draft, hit a saturation stop, and propose a
weight update after a scripted scorecard. README narrates the loop and links
each visible decision to its test.

## 8. Stack

Python 3.12, pytest, SQLite (stdlib `sqlite3`), Streamlit, OpenRouter
(structured extraction + drafting), Gmail API, python-dotenv. **No agent
framework** — the loop is the project.

## 9. Explicitly out of scope (v1)

- Sending outreach (email/contact-form integration) — drafts only.
- Building-shadow light modeling from footprint geometry — v2.
- Any scraping or third-party scraper APIs.
- Hosted deployment.
- Sale listings, roommate matching, other cities.

## 10. Open items

- Project name (working: apartment-search).
- User's actual criteria weights + train line (captured in the cold-start
  interview, not hardcoded).
- StreetEasy alert-email HTML structure — needs a real sample capture before
  the parser is specced in the implementation plan.
