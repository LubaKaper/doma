# TDD.md — Testing Discipline

How this project is tested, and the rules every change follows.
The implementation plans encode these as explicit steps; this file is the
standing policy.

## The cycle (non-negotiable)

Every behavior change follows red → green → commit:

1. Write the failing test first.
2. Run it; confirm it fails for the expected reason (not an import typo).
3. Write the minimal implementation to pass.
4. Run the test; confirm green.
5. Run the full suite; confirm no regressions.
6. Commit (one logical change per commit).

No implementation code lands without a test that failed before it existed.

## Test layers

| Layer | What it proves | Where |
|---|---|---|
| Unit | Each stopping rule, policy priority, projection fold, adapter parse — as pure functions | `tests/test_<module>.py` |
| Replay integration | The loop's *decisions* over a recorded corpus: "saturation fires on day X", "budget never exceeded", "two runs are identical" | `tests/test_replay.py` |
| Property-style checks | Invariants: weights normalized, terminal listings never receive actions, confidence monotone in fact count | alongside unit tests |

## Hard rules

- **No network in tests. Ever.** Adapters are tested against fixture payloads;
  the loop is tested via replay corpora. If a test needs the internet, the
  design is wrong.
- **Determinism is a tested feature.** Replay runs are asserted identical.
  Anything nondeterministic (LLM calls, live clocks) lives behind an injected
  boundary (Executor, Clock) and is replaced in tests.
- **Fixtures are honest.** Real captured API responses/emails, sanitized
  (addresses fuzzed, personal data stripped). Synthetic fixtures are allowed
  only when clearly labeled synthetic (e.g. `corpus_smoke.jsonl`) and are
  schema-faithful. Never invent field names — capture a real payload and look.
- **Don't weaken assertions to go green.** A failing replay assertion means
  the loop is wrong (or the assertion encodes a spec misreading — fix the
  spec conversation, not the number).
- **Missing data tests are mandatory.** Every scorer/parser gets at least one
  test where a field is `None` and the assertion proves it stayed `None`
  (confidence may drop; values never get invented).

## Commands

```bash
# full suite
.venv/bin/python -m pytest -v

# one module
.venv/bin/python -m pytest tests/test_policy.py -v

# one test
.venv/bin/python -m pytest tests/test_policy.py::test_decide_priority_saturation_before_scan -v
```

## Definition of done (any task)

- New behavior has a test that failed first.
- Full suite green.
- No `print()` debugging left; no silent except blocks.
- Docs updated if the change was substantial (see AGENTS.md §Docs contract).
