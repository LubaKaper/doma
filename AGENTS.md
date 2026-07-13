# AGENTS.md — Instructions for AI agents working in this repo

You are working on the NYC apartment-hunt agent. Read this file first, then
`STATUS.md` for where things stand. A new session should need nothing beyond
these files and the docs they point to.

## Read in this order

1. `STATUS.md` — current state, next action, decision log. **Always start here.**
2. `prd.md` — what we're building and why; scope and non-goals.
3. `docs/superpowers/specs/2026-07-11-apartment-hunt-agent-design.md` — the
   approved design (architecture, components, event types). If docs conflict,
   the spec wins.
4. The active implementation plan in `docs/superpowers/plans/` — complete
   TDD tasks with code; execute from there, don't improvise.
5. `TDD.md` — testing discipline for any change not covered by a plan.

## Project shape

- **What:** event-sourced deterministic tick loop that hunts NYC apartments.
  Policy function decides actions; stopping rules are first-class; LLM only
  extracts facts and drafts outreach — it never decides anything.
- **Package:** `src/doma/` (project name: Doma) (module map in the plan's File Structure section).
- **Stack:** Python 3.12, stdlib sqlite3, pytest; later plans add Streamlit,
  OpenRouter, Gmail API. No agent frameworks.
- **Modes:** live (real APIs, real clock) and replay (recorded input events,
  decisions recomputed) — same loop, injected Clock + Executor.

## Hard rules

1. **TDD always.** Failing test first. See `TDD.md`.
2. **Honest data.** Missing values are `None`, never imputed. Never invent
   API field names — capture a real payload and look.
3. **No scraping.** RentCast API, own-inbox email parsing, NYC Open Data,
   GTFS only. This is a product decision; do not add scraper adapters.
4. **Determinism boundaries.** Anything nondeterministic (network, time, LLM)
   goes behind an injected interface (Executor, Clock) so replay stays exact.
5. **No outreach sending.** Drafts only, human-approved. v1 has no sending
   integration at all.
6. **No PRs.** Commit locally on the current branch; the user handles
   PRs/pushes manually when ready.
7. **No silent except blocks; every error message names the failing
   file/source.** Type hints on every signature; docstrings on public
   functions.
8. **Event store is append-only.** Never mutate state outside it; `project()`
   and `decide()` stay pure.

## Docs contract (keep these current)

After every **substantial** change (a completed plan task or group of tasks,
a design decision, a scope change), update in the same commit or an
immediately following `docs:` commit:

- `STATUS.md` — always: state, next action, decision log entry if a decision
  was made.
- `prd.md` — only if scope/requirements changed.
- Spec/plan docs — only if the design or plan changed (spec changes need
  user approval first).
- `README.md` — only if setup/run instructions changed.
- This file — only if working rules changed.

The bar: a fresh agent session reading `STATUS.md` must be able to continue
the work without the user re-explaining anything.

## Commands

```bash
cd /Users/lubakaper/Desktop/L3Projects/apartment-search
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt  # first time
.venv/bin/python -m pytest -v                                        # full suite
./doma replay tests/fixtures/corpus_smoke.jsonl \
  --start 2026-07-01T00:00:00+00:00 --until 2026-07-15T00:00:00+00:00
# ./doma is the launcher — use it over `python -m doma` (this machine's
# Python ignores editable-install .pth files; the launcher sets PYTHONPATH)
```

## Git conventions

- Commit format: `type(scope): description` — types: feat, fix, refactor,
  docs, test, chore. Example: `feat(policy): add saturation stopping rule`.
- One logical change per commit. Commit after every green task step.
- Branch: work on `main` until the user says otherwise (solo repo).
