# apartment-search — NYC Apartment-Hunt Agent

An autonomous apartment-hunting loop for NYC: **scan → score → outreach draft
→ preference feedback**, built as a deliberate exercise in *loop engineering*
— the evaluator, the decision policy, and the stopping rules are the project.

> **Thesis:** every decision is a tested function. The LLM only reads
> (extracting facts from messy listing text) and writes (drafting inquiries);
> it never decides anything. No agent frameworks — the loop is ~200 lines of
> tested Python.

## What it does

- **Scans** ToS-clean sources: the official [RentCast API](https://www.rentcast.io/api)
  and StreetEasy saved-search alert emails from the user's own inbox — plus
  NYC Open Data (HPD violations, DOB complaints) and MTA GTFS for enrichment.
  **No scraping, anywhere.** (Researched the alternatives; the README of a
  portfolio project shouldn't come with a ToS violation.)
- **Scores** each listing against real criteria (rent value, light, laundry,
  commute, building health, fee burden) with confidence from fact
  completeness. Unknown facts stay unknown — nothing is imputed.
- **Detects bait:** relisted units with reset days-on-market, "no fee" claims
  contradicted by fee facts, price-drop laddering — each flag carries its
  evidence trail.
- **Drafts inquiries** for human approval. Nothing is ever sent automatically.
- **Learns** from post-viewing scorecards: per-criterion residuals propose
  bounded weight updates that apply only after the user approves the diff —
  with a full audit history of how the taste model evolved.

## Architecture in one paragraph

Everything that happens is an event in an append-only SQLite store. State is
a pure projection of events. Each tick, a pure `decide()` function ranks
candidate actions under first-class **stopping rules** — per-listing terminal
states, neighborhood saturation, monthly API budgets, an outreach confidence
gate. Live mode feeds real time and real APIs; **replay mode** feeds recorded
input events at accelerated time while decisions are recomputed by the same
code — which makes the loop's behavior assertable in pytest ("saturation
fires on day 11", "budget never exceeded", "two runs are byte-identical").

## Status

🚧 Early development. Design and Plan 1 (core loop) are complete; see
[STATUS.md](STATUS.md) for exact state and
[the design spec](docs/superpowers/specs/2026-07-11-apartment-hunt-agent-design.md)
for the full architecture.

## Run

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -v        # the loop's behavior, asserted
```

Replay demo (offline, no API keys) — available once Plan 1 ships:

```bash
.venv/bin/python -m hunt replay tests/fixtures/corpus_smoke.jsonl \
  --start 2026-07-01T00:00:00+00:00 --until 2026-07-15T00:00:00+00:00
```

## Roadmap

1. **Core loop** — event store, projection, policy + stopping rules, replay harness ← *current*
2. **Sources & scoring** — adapters, relist detection, scorer, bait detector, LLM fact extraction
3. **Learning, outreach, UI** — preference learner, outreach drafter, Streamlit dashboard, golden demo corpus

## Prior work

Built with the same standards as [Fourth](https://github.com/LubaKaper/FOURTH):
honest data, deterministic guardrails, tests before code, human approval
before anything leaves the system.
