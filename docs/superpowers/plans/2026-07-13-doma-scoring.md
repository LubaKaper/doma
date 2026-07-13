# Doma Scoring & Bait Implementation Plan (Plan 3 of 4)

> Executed inline by the authoring session (same TDD discipline: failing
> test → implement → green → commit). This plan records contracts and
> decisions; the code lives in the commits referencing it.

**Goal:** Every active listing gets a score with confidence, HPD + commute
enrichment flows through the policy ladder, and bait (relists, price
laddering, fee contradictions) is flagged with evidence. `doma rank` shows
the ranked market; `doma run --ticks N` drives the live loop end to end.

**Scope decision:** LLM fact extraction is DEFERRED to the email-parser
milestone — RentCast payloads carry no free text, so extraction has no input
yet. Laundry/light subscores stay `None` (lower confidence, never guessed).

## Design

### Data flow additions
- `Snapshot` gains `lat`/`lon` (optional, default None — RentCast provides
  them; the differ passes them through; projection stores them).
- `ListingState` gains: `address`, `unit`, `fee`, `lat`, `lon`,
  `price_history` (list of `[ts, price]`), `hpd` (dict|None), `commute`
  (dict|None), `score`, `score_confidence`, `score_ts`,
  `enrich_attempted_ts`, `bait_flags` (list of kinds).
- New decision event type: `enrichment_attempted` (bookkeeping so the policy
  never re-enriches endlessly; payload notes ok/error per listing).

### Scorer (`doma/scorer.py`) — pure functions
- `DEFAULT_WEIGHTS`: rent_value .30, commute .25, building_health .20,
  laundry .10, light .10, fee_burden .05.
- Subscores in [0,1] or None (unknown stays unknown):
  - rent_value: `clamp(0.5 + (median − price)/median)` vs the neighborhood
    median of active priced listings (needs ≥5 samples, else None).
  - commute: walk ≤300 m → 1.0, ≥1500 m → 0.0, linear between.
  - building_health: `1/(1 + 0.1·A + 0.3·B + 0.6·C)` from HPD open-violation
    class counts.
  - fee_burden: False → 1.0, True → 0.2, None → None.
  - laundry, light: None until facts exist (post-email extraction).
- `score = Σ wᵢsᵢ / Σ wᵢ` over KNOWN subscores;
  `confidence = Σ w(known) / Σ w(all)`. No known subscores → no score event.

### Bait (`doma/bait.py`) — deterministic rules with evidence
- `relist`: `relist_count ≥ 1`; evidence = count + price history.
- `price_laddering`: ≥2 consecutive price drops in `price_history`.
- `fee_contradiction`: reserved (needs facts); rule present, fires only when
  a "no fee" claim coexists with `fee is True`.
- Emitted as `bait_flagged` once per (listing, kind) — projection dedupes.

### Policy ladder (updated priority)
mark_saturated → **enrich_batch** (any active listing with
`enrich_attempted_ts is None`) → **score_batch** (any active listing whose
`last activity > score_ts`) → scan_rentcast (budgeted) → sleep.
`PolicyConfig` gains `enrich_batch_size` (default 20).

### Execution
- `score_batch` is pure and shared (`actions.score_batch_events`): identical
  in live and replay — decisions are recomputed, never recorded.
- `enrich_batch` in live mode calls injected `hpd_fetch(listing)` and
  `commute_fn(listing)` callables (real ones wired in the CLI; tests inject
  fakes — no network in tests, ever). Per-listing failures produce
  `enrichment_attempted` with the error message; the loop never crashes.
- `enrich_batch` in replay mode delivers the corpus's recorded
  `enrichment_added` events for the targeted listings.
- Borough for HPD queries derives from the zip prefix
  (`doma/adapters/hpd.py: borough_from_zip`).

### CLI
- `doma run --ticks N --city Brooklyn` — run N live ticks (scan only fires
  if due + budgeted; enrichment/scoring fill the rest).
- `doma rank --top 15` — ranked table: score, confidence, price, address,
  zip, walk, bait flags.

### Tests (all failing-first)
- scorer: each subscore incl. None-propagation; median threshold; weight
  renormalization; confidence math.
- bait: relist fires with evidence; laddering needs ≥2 drops; no flags on
  clean listings; dedupe via projection.
- state: price_history append; enrichment/score/bait folds; attempted fold.
- policy: new ladder order (enrich before score before scan); batch caps.
- live: enrich_batch with fake enrichers, including one that raises.
- replay: enrich_batch delivers corpus enrichment for targets only.

### Done criteria
- Full suite green, no network in tests.
- `doma run --ticks 40` on the real db enriches + scores real listings.
- `doma rank` shows scored, flagged listings from the user's real scan.
- Deferred: LLM extraction module (needs email text), Gmail live fetch,
  de-saturation.
