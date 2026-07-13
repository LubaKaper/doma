"""Doma dashboard: the event store, projected and readable.

Thin shell: all data logic lives in doma.*; the UI reads projections and
appends validated events (decisions.py). Run: streamlit run app.py
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))  # editable-pth quirk guard

import streamlit as st

from doma.decisions import mark_listing_event, scorecard_event
from doma.events import iso
from doma.scorer import DEFAULT_WEIGHTS
from doma.state import ListingState, project
from doma.store import EventStore

# Single sequential hue for magnitude; gray for unknown; status red for bait.
BAR_HUE = "#2563eb"
BAR_UNKNOWN = "#d4d4d8"
INK_MUTED = "#71717a"

st.set_page_config(page_title="Doma", page_icon="🏠", layout="wide")


def _now_iso() -> str:
    return iso(datetime.now(timezone.utc))


def _subscore_bars(listing: ListingState) -> str:
    """Horizontal magnitude bars; unknown criteria render as labeled gaps."""
    rows = []
    for criterion in DEFAULT_WEIGHTS:
        value = listing.subscores.get(criterion)
        label = criterion.replace("_", " ")
        if value is None:
            bar = (f'<div style="background:{BAR_UNKNOWN};width:100%;height:6px;'
                   f'border-radius:4px;opacity:.5"></div>')
            val = f'<span style="color:{INK_MUTED}">unknown</span>'
        else:
            pct = round(float(value) * 100)
            bar = (f'<div style="background:#e4e4e7;width:100%;height:6px;'
                   f'border-radius:4px"><div style="background:{BAR_HUE};'
                   f'width:{pct}%;height:6px;border-radius:4px"></div></div>')
            val = f"{value:.2f}"
        rows.append(
            f'<div style="display:grid;grid-template-columns:110px 1fr 52px;'
            f'gap:10px;align-items:center;margin:4px 0;font-size:13px">'
            f'<span style="color:{INK_MUTED}">{label}</span>{bar}'
            f'<span style="text-align:right">{val}</span></div>')
    return "".join(rows)


def _title_line(listing: ListingState) -> str:
    price = f"${listing.price:,}" if listing.price else "$?"
    addr = f"{listing.address or listing.listing_id} {listing.unit or ''}".strip()
    score = (f"{listing.score:.2f}" if listing.score is not None else "—")
    conf = (f"{listing.score_confidence:.0%}"
            if listing.score_confidence is not None else "?")
    flag = f"  ⚠️ {', '.join(listing.bait_flags)}" if listing.bait_flags else ""
    return f"{score} · {price} · {addr} · {listing.neighborhood} · conf {conf}{flag}"


def _mark(store: EventStore, listing_id: str, status: str) -> None:
    store.append(mark_listing_event(listing_id, status, ts=_now_iso()))
    st.rerun()


def _listing_card(store: EventStore, listing: ListingState) -> None:
    with st.expander(_title_line(listing)):
        left, right = st.columns([3, 2], gap="large")
        with left:
            st.markdown("**Why this score**")
            st.markdown(_subscore_bars(listing), unsafe_allow_html=True)
            if listing.bait_flags:
                st.warning("Bait signals: " + ", ".join(listing.bait_flags)
                           + f" — relisted {listing.relist_count}× "
                           if listing.relist_count else
                           "Bait signals: " + ", ".join(listing.bait_flags))
            if len(listing.price_history) > 1:
                st.markdown("**Price history**")
                st.table({"when": [h[0][:10] for h in listing.price_history],
                          "price": [f"${h[1]:,}" for h in listing.price_history]})
        with right:
            st.markdown("**Facts**")
            hpd = listing.hpd or {}
            st.markdown(
                f"- HPD open violations: "
                f"{hpd.get('total', '?')} "
                f"(A {hpd.get('class_a', '?')} · B {hpd.get('class_b', '?')} · "
                f"C {hpd.get('class_c', '?')})\n"
                f"- Nearest subway: "
                f"{(listing.commute or {}).get('station', 'unknown')} "
                f"({(listing.commute or {}).get('walk_meters', '?')} m)\n"
                f"- Fee: {'no fee' if listing.fee is False else 'fee' if listing.fee else 'unknown'}\n"
                f"- First seen: {listing.first_seen_ts[:10]} · "
                f"last seen: {listing.last_seen_ts[:10]}")
            b1, b2, b3 = st.columns(3)
            if b1.button("⭐ Pursue", key=f"p-{listing.listing_id}",
                         use_container_width=True):
                _mark(store, listing.listing_id, "pursuing")
            if b2.button("👁 Viewed", key=f"v-{listing.listing_id}",
                         use_container_width=True):
                _mark(store, listing.listing_id, "viewed")
            if b3.button("✕ Reject", key=f"r-{listing.listing_id}",
                         use_container_width=True):
                _mark(store, listing.listing_id, "rejected")


def _scorecard_form(store: EventStore, listing: ListingState) -> None:
    with st.form(key=f"sc-{listing.listing_id}"):
        st.markdown(f"**{listing.address or listing.listing_id}** — "
                    "rate what you actually experienced (skip = unknown)")
        verdict = st.radio("Verdict", ["pursue", "pass"], horizontal=True,
                           key=f"vd-{listing.listing_id}")
        ratings: dict[str, int] = {}
        cols = st.columns(3)
        for i, criterion in enumerate(DEFAULT_WEIGHTS):
            with cols[i % 3]:
                val = st.select_slider(
                    criterion.replace("_", " "),
                    options=["skip", 1, 2, 3, 4, 5], value="skip",
                    key=f"sl-{listing.listing_id}-{criterion}")
                if val != "skip":
                    ratings[criterion] = int(val)
        if st.form_submit_button("Save scorecard"):
            store.append(scorecard_event(listing.listing_id, verdict,
                                         ratings, ts=_now_iso()))
            st.success("Saved — this feeds the preference learner.")
            st.rerun()


def main() -> None:
    db_default = os.environ.get("DOMA_DB", "doma.db")
    st.sidebar.title("🏠 Doma")
    db_path = st.sidebar.text_input("Event store", db_default)
    if not Path(db_path).exists():
        st.info(f"No event store at `{db_path}` yet — run "
                "`.venv/bin/python -m doma run` first.")
        return
    store = EventStore(db_path)
    state = project(store.read_all())

    month = datetime.now(timezone.utc).strftime("%Y-%m")
    active = [l for l in state.listings.values() if l.status == "active"]
    flagged = [l for l in state.listings.values() if l.bait_flags]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Active listings", len(active))
    m2.metric("Scored", sum(1 for l in active if l.score is not None))
    m3.metric("Bait flagged", len(flagged))
    m4.metric("API budget", f"{state.scan_months.get(month, 0)}/40",
              help="RentCast scans used this calendar month")
    if state.saturated:
        st.caption("Saturated (scanning stopped): "
                   + ", ".join(sorted(state.saturated)))

    tab_rank, tab_mine, tab_activity = st.tabs(
        ["Ranked", "My decisions", "Activity"])

    with tab_rank:
        f1, f2, f3 = st.columns([2, 2, 1])
        max_price = f1.slider("Max price", 500, 10000, 4000, step=100)
        min_conf = f2.slider("Min confidence", 0.0, 1.0, 0.0, step=0.05)
        hide_flagged = f3.checkbox("Hide flagged", value=False)
        ranked = sorted(
            (l for l in active
             if l.score is not None
             and (l.price is None or l.price <= max_price)
             and (l.score_confidence or 0) >= min_conf
             and not (hide_flagged and l.bait_flags)),
            key=lambda l: (-(l.score or 0), -(l.score_confidence or 0),
                           l.price or 10**9))
        if not ranked:
            st.info("Nothing matches these filters.")
        for listing in ranked[:25]:
            _listing_card(store, listing)

    with tab_mine:
        for status, label in (("pursuing", "⭐ Pursuing"),
                              ("viewed", "👁 Viewed — log a scorecard"),
                              ("rejected", "✕ Rejected")):
            group = [l for l in state.listings.values() if l.status == status]
            st.subheader(f"{label} ({len(group)})")
            for listing in group:
                if status == "viewed" and listing.scorecard is None:
                    _scorecard_form(store, listing)
                else:
                    line = _title_line(listing)
                    if listing.scorecard:
                        line += f"  · scorecard: {listing.scorecard['verdict']}"
                    st.markdown(f"- {line}")
                    if st.button("↩ back to active",
                                 key=f"ba-{listing.listing_id}"):
                        _mark(store, listing.listing_id, "active")

    with tab_activity:
        events = store.read_all()
        st.caption(f"{len(events)} events in the store")
        for e in reversed(events[-40:]):
            st.text(f"{e.ts[:19]}  {e.type:22} "
                    f"{e.payload.get('listing_id', e.payload.get('neighborhood', ''))}")


main()
