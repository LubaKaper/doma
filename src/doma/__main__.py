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


def _live_executor(db: str, city: str, state_code: str) -> tuple:
    """Build a LiveExecutor with real fetcher + enrichers. Needs .env key."""
    import os
    import time
    from pathlib import Path

    from dotenv import load_dotenv

    from doma.adapters.hpd import (borough_from_zip, fetch_open_violations,
                                   summarize)
    from doma.adapters.rentcast import fetch_listings, to_snapshot
    from doma.adapters.stations import load_stations, nearest_station
    from doma.clock import LiveClock
    from doma.live import LiveExecutor
    from doma.snapshot import Snapshot

    load_dotenv()
    api_key = os.environ.get("RENTCAST_API_KEY", "")
    if not api_key:
        raise SystemExit("RENTCAST_API_KEY not set (see .env.example)")
    store = EventStore(db)

    def fetch() -> list[Snapshot]:
        return [to_snapshot(r)
                for r in fetch_listings(api_key, city, state_code)]

    stations = load_stations(Path(__file__).parent.parent.parent / "tests"
                             / "fixtures" / "stations_sample.json")

    def hpd_fetch(listing) -> dict | None:
        if listing.address is None:
            return None
        boro = borough_from_zip(listing.neighborhood)
        if boro is None:
            return None
        housenumber = listing.address.split()[0]
        street = " ".join(listing.address.split()[1:])
        time.sleep(0.1)  # be gentle with the open-data API
        return summarize(fetch_open_violations(housenumber, street, boro))

    def commute_fn(listing) -> dict | None:
        if listing.lat is None or listing.lon is None:
            return None
        station, meters = nearest_station(listing.lat, listing.lon, stations)
        return {"station": station.name, "walk_meters": round(meters)}

    clock = LiveClock()
    executor = LiveExecutor(store=store, fetcher=fetch, clock=clock,
                            sleep_seconds=0, hpd_fetch=hpd_fetch,
                            commute_fn=commute_fn)
    return store, executor, clock


def _cmd_scan(args: argparse.Namespace) -> None:
    """Run one live tick; the policy decides what actually happens."""
    from doma.loop import run_tick

    store, executor, clock = _live_executor(args.db, args.city, args.state)
    action, events = run_tick(store, PolicyConfig(), executor, clock)
    print(f"decision: {action.type} ({action.reason})")
    print(f"{len(events)} events appended to {args.db}")


def _cmd_run(args: argparse.Namespace) -> None:
    """Run N live ticks; stops early once the loop settles into sleep."""
    from doma.loop import run_tick

    store, executor, clock = _live_executor(args.db, args.city, args.state)
    for tick in range(1, args.ticks + 1):
        action, events = run_tick(store, PolicyConfig(), executor, clock)
        print(f"tick {tick:3}  {action.type:16} {action.reason}"
              f"  (+{len(events)} events)")
        if action.type == "sleep":
            print("loop settled — nothing left to do right now")
            break


def _cmd_rank(args: argparse.Namespace) -> None:
    """Ranked view of scored listings: the market as Doma sees it."""
    from doma.state import project

    state = project(EventStore(args.db).read_all())
    scored = [l for l in state.listings.values()
              if l.status == "active" and l.score is not None]
    scored.sort(key=lambda l: l.score, reverse=True)
    print(f"{'score':>5} {'conf':>5} {'price':>7} {'walk':>6}  "
          f"{'address':32} {'zip':5} flags")
    for l in scored[:args.top]:
        walk = (f"{l.commute['walk_meters']}m"
                if l.commute and l.commute.get("walk_meters") is not None
                else "?")
        flags = ",".join(l.bait_flags) or "-"
        addr = f"{l.address or '?'} {l.unit or ''}".strip()
        print(f"{l.score:5.2f} {l.score_confidence:5.2f} "
              f"{'$' + str(l.price) if l.price else '?':>7} {walk:>6}  "
              f"{addr:32.32} {l.neighborhood:5} {flags}")
    unscored = sum(1 for l in state.listings.values()
                   if l.status == 'active' and l.score is None)
    print(f"\n{len(scored)} scored, {unscored} unscored, "
          f"{sum(1 for l in state.listings.values() if l.bait_flags)} flagged")


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

    rn = sub.add_parser("run", help="run N live ticks (enrich/score/scan)")
    rn.add_argument("--db", default="doma.db")
    rn.add_argument("--city", default="Brooklyn")
    rn.add_argument("--state", default="NY")
    rn.add_argument("--ticks", type=int, default=40)

    rk = sub.add_parser("rank", help="ranked view of scored listings")
    rk.add_argument("--db", default="doma.db")
    rk.add_argument("--top", type=int, default=15)

    args = parser.parse_args()
    if args.command == "replay":
        _cmd_replay(args)
    elif args.command == "scan":
        _cmd_scan(args)
    elif args.command == "export-corpus":
        _cmd_export_corpus(args)
    elif args.command == "run":
        _cmd_run(args)
    elif args.command == "rank":
        _cmd_rank(args)


if __name__ == "__main__":
    main()
