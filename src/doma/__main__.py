"""CLI entry point: `python -m doma replay <corpus.jsonl> --start ... --until ...`."""
from __future__ import annotations

import argparse

from doma.clock import ReplayClock
from doma.corpus import load_corpus
from doma.events import parse_ts
from doma.policy import PolicyConfig
from doma.replay import run_replay
from doma.store import EventStore


def main() -> None:
    """Parse args and run a replay, printing every non-sleep decision."""
    parser = argparse.ArgumentParser(prog="doma")
    sub = parser.add_subparsers(dest="command", required=True)
    rp = sub.add_parser("replay", help="replay a recorded input corpus")
    rp.add_argument("corpus", help="path to a JSONL input-event corpus")
    rp.add_argument("--start", required=True,
                    help="sim start, ISO 8601 (e.g. 2026-07-01T00:00:00+00:00)")
    rp.add_argument("--until", required=True,
                    help="sim end, ISO 8601")
    args = parser.parse_args()

    corpus = load_corpus(args.corpus)
    store = EventStore(":memory:")
    clock = ReplayClock(start=parse_ts(args.start))
    actions = run_replay(store, PolicyConfig(), corpus, clock,
                         until=parse_ts(args.until))

    decisions = [a for a in actions if a.type != "sleep"]
    for action in decisions:
        print(f"{action.type:16} {action.target or '-':16} {action.reason}")
    print(f"\n{len(actions)} ticks, {len(decisions)} decisions, "
          f"{len(store.read_all())} events")


if __name__ == "__main__":
    main()
