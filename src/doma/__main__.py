"""CLI entry point: replay a corpus, run a live scan, or export a corpus."""
from __future__ import annotations

import argparse

from doma.clock import ReplayClock
from doma.corpus import load_corpus
from doma.events import parse_ts
from doma.policy import PolicyConfig
from doma.replay import run_replay
from doma.store import EventStore


def _cmd_replay(args: argparse.Namespace) -> None:
    """Replay a recorded corpus, printing every non-sleep decision."""
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


def _cmd_scan(args: argparse.Namespace) -> None:
    """Run one live tick against RentCast; the policy may decline to scan."""
    import os

    from dotenv import load_dotenv

    from doma.adapters.rentcast import fetch_listings, to_snapshot
    from doma.clock import LiveClock
    from doma.live import LiveExecutor
    from doma.loop import run_tick
    from doma.snapshot import Snapshot

    load_dotenv()
    api_key = os.environ.get("RENTCAST_API_KEY", "")
    if not api_key:
        raise SystemExit("RENTCAST_API_KEY not set (see .env.example)")
    store = EventStore(args.db)

    def fetch() -> list[Snapshot]:
        return [to_snapshot(r)
                for r in fetch_listings(api_key, args.city, args.state)]

    clock = LiveClock()
    executor = LiveExecutor(store=store, fetcher=fetch, clock=clock,
                            sleep_seconds=0)
    action, events = run_tick(store, PolicyConfig(), executor, clock)
    print(f"decision: {action.type} ({action.reason})")
    print(f"{len(events)} events appended to {args.db}")


def _cmd_export_corpus(args: argparse.Namespace) -> None:
    """Dump a database's input events as a JSONL corpus for replay."""
    from doma.corpus import save_corpus
    from doma.events import INPUT_EVENT_TYPES

    store = EventStore(args.db)
    inputs = [e for e in store.read_all() if e.type in INPUT_EVENT_TYPES]
    save_corpus(inputs, args.out)
    print(f"wrote {len(inputs)} input events to {args.out}")


def main() -> None:
    """Parse args and dispatch to a subcommand."""
    parser = argparse.ArgumentParser(prog="doma")
    sub = parser.add_subparsers(dest="command", required=True)

    rp = sub.add_parser("replay", help="replay a recorded input corpus")
    rp.add_argument("corpus", help="path to a JSONL input-event corpus")
    rp.add_argument("--start", required=True,
                    help="sim start, ISO 8601 (e.g. 2026-07-01T00:00:00+00:00)")
    rp.add_argument("--until", required=True,
                    help="sim end, ISO 8601")

    sc = sub.add_parser("scan", help="one live RentCast scan into the db")
    sc.add_argument("--db", default="doma.db", help="event store path")
    sc.add_argument("--city", required=True)
    sc.add_argument("--state", default="NY")

    xc = sub.add_parser("export-corpus",
                        help="dump the db's input events as a JSONL corpus")
    xc.add_argument("--db", default="doma.db")
    xc.add_argument("out", help="output corpus path")

    args = parser.parse_args()
    if args.command == "replay":
        _cmd_replay(args)
    elif args.command == "scan":
        _cmd_scan(args)
    elif args.command == "export-corpus":
        _cmd_export_corpus(args)


if __name__ == "__main__":
    main()
