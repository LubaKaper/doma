"""Doma dashboard — a daily apartment-hunting cockpit.

Flow: Today (decide fast) -> Browse (dig deeper) -> Saved (message + visit)
-> Visited (tell Doma how it was) -> Your taste (approve what it learned).
The UI stays a thin shell: it reads projections and appends validated events.
System internals live behind "Under the hood" in the sidebar.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))  # editable-pth quirk guard

import streamlit as st
from dotenv import load_dotenv

from doma.decisions import (mark_listing_event, scorecard_event,
                            weights_updated_event)
from doma.events import Event, iso
from doma.humanize import BAIT_LABELS, chips, fit_label, knowledge_label
from doma.learner import MIN_RATINGS, propose_weights
from doma.outreach import draft_outreach
from doma.state import ListingState, project
from doma.store import EventStore

st.set_page_config(page_title="Doma", page_icon="🏠", layout="wide")

CRITERIA_QUESTIONS = {
    "rent_value": "Worth the price?",
    "commute": "The trip there?",
    "building_health": "Building condition?",
    "laundry": "Laundry situation?",
    "light": "Natural light?",
    "fee_burden": "Fees & costs?",
}
PLACEHOLDER_TONES = ["#dbeafe", "#fce7f3", "#dcfce7", "#fef3c7", "#ede9fe"]


def _now_iso() -> str:
    return iso(datetime.now(timezone.utc))


def _mark(store: EventStore, listing_id: str, status: str) -> None:
    store.append(mark_listing_event(listing_id, status, ts=_now_iso()))
    st.rerun()


def _photo(listing: ListingState) -> None:
    if listing.photo_url:
        st.image(listing.photo_url, use_container_width=True)
    else:
        tone = PLACEHOLDER_TONES[hash(listing.listing_id)
                                 % len(PLACEHOLDER_TONES)]
        label = (listing.neighborhood or "?").title()
        st.markdown(
            f'<div style="background:{tone};border-radius:12px;height:150px;'
            f'display:flex;align-items:center;justify-content:center;'
            f'color:#525252;font-size:15px">No photo · {label}</div>',
            unsafe_allow_html=True)


def _headline(listing: ListingState) -> str:
    price = f"${listing.price:,}/mo" if listing.price else "Price unknown"
    addr = f"{listing.address or listing.listing_id}"
    if listing.unit:
        addr += f" · #{listing.unit}"
    return f"**{price}** — {addr}"


def _verdict_line(listing: ListingState) -> str:
    return (f"{fit_label(listing.score)} · "
            f"{knowledge_label(listing.score_confidence)}")


def _bait_warning(listing: ListingState) -> None:
    if listing.bait_flags:
        reasons = "; ".join(BAIT_LABELS.get(f, f) for f in listing.bait_flags)
        st.error(f"Careful: {reasons}", icon="⚠️")


def _details(listing: ListingState) -> None:
    with st.expander("More detail"):
        source = ("StreetEasy alert" if "email" in listing.source
                  else "RentCast")
        st.markdown(
            f"- Neighborhood: {(listing.neighborhood or '?').title()}\n"
            f"- Source: {source}\n"
            f"- First seen {listing.first_seen_ts[:10]}, "
            f"last seen {listing.last_seen_ts[:10]}")
        if len(listing.price_history) > 1:
            st.caption("Price history")
            st.table({"date": [h[0][:10] for h in listing.price_history],
                      "price": [f"${h[1]:,}" for h in listing.price_history]})


def _decision_card(store: EventStore, listing: ListingState,
                   key_prefix: str) -> None:
    """One place, one decision: Save it or Skip it."""
    with st.container(border=True):
        photo_col, body = st.columns([1, 2], gap="medium")
        with photo_col:
            _photo(listing)
        with body:
            st.markdown(_headline(listing))
            card_chips = chips(listing)
            if card_chips:
                st.markdown(" · ".join(card_chips))
            st.caption(_verdict_line(listing))
            _bait_warning(listing)
            save, skip, _sp = st.columns([1, 1, 2])
            if save.button("♥ Save", key=f"{key_prefix}-s-{listing.listing_id}",
                           use_container_width=True, type="primary"):
                _mark(store, listing.listing_id, "pursuing")
            if skip.button("Skip", key=f"{key_prefix}-x-{listing.listing_id}",
                           use_container_width=True):
                _mark(store, listing.listing_id, "rejected")
            _details(listing)


def _tab_today(store: EventStore, undecided: list[ListingState]) -> None:
    clean = [l for l in undecided if not l.bait_flags]
    suspicious = [l for l in undecided if l.bait_flags]
    if not undecided:
        st.success("All caught up — nothing new needs a decision. "
                   "Doma keeps watching.")
        return
    st.markdown(f"#### {len(undecided)} places waiting for your call")
    st.caption("Best matches first. Save what looks promising, skip the "
               "rest — every choice teaches Doma your taste.")
    for listing in clean[:8]:
        _decision_card(store, listing, "today")
    remaining = len(clean) - min(len(clean), 8)
    if remaining > 0:
        st.caption(f"{remaining} more in the Browse tab.")
    if suspicious:
        with st.expander(f"⚠️ {len(suspicious)} places look like bait — "
                         "view anyway"):
            for listing in suspicious[:10]:
                _decision_card(store, listing, "bait")


def _tab_browse(store: EventStore, undecided: list[ListingState]) -> None:
    f1, f2, f3 = st.columns([2, 1, 1])
    max_price = f1.slider("Max price", 500, 10000, 4000, step=100)
    sort = f2.selectbox("Sort by", ["Best fit", "Cheapest", "Newest"])
    show_bait = f3.checkbox("Include bait", value=False)
    rows = [l for l in undecided
            if (l.price is None or l.price <= max_price)
            and (show_bait or not l.bait_flags)]
    if sort == "Cheapest":
        rows.sort(key=lambda l: l.price or 10**9)
    elif sort == "Newest":
        rows.sort(key=lambda l: l.first_seen_ts, reverse=True)
    st.caption(f"{len(rows)} places")
    for listing in rows[:30]:
        _decision_card(store, listing, "browse")


def _tab_saved(store: EventStore, state) -> None:
    saved = [l for l in state.listings.values() if l.status == "pursuing"]
    if not saved:
        st.info("Nothing saved yet — hit ♥ Save on places you like in "
                "Today or Browse.")
        return
    st.caption("Your shortlist. Get a message drafted, send it from your "
               "own email (Doma never sends anything), then log your visit.")
    load_dotenv()
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    for listing in saved:
        with st.container(border=True):
            photo_col, body = st.columns([1, 2], gap="medium")
            with photo_col:
                _photo(listing)
            with body:
                st.markdown(_headline(listing))
                card_chips = chips(listing)
                if card_chips:
                    st.markdown(" · ".join(card_chips))
                _bait_warning(listing)
                if listing.outreach is None:
                    if st.button("✍️ Write my inquiry message",
                                 key=f"d-{listing.listing_id}"):
                        with st.spinner("Drafting…"):
                            draft, method, error = draft_outreach(api_key,
                                                                  listing)
                        store.append(Event(
                            ts=_now_iso(), type="outreach_proposed",
                            payload={"listing_id": listing.listing_id,
                                     "draft": draft,
                                     "generation_method": method,
                                     "error": error}))
                        st.rerun()
                else:
                    st.caption("Copy this, personalize the sign-off, and "
                               "send it yourself:")
                    st.code(listing.outreach.get("draft", ""), language=None)
                visit, unsave, _sp = st.columns([1, 1, 2])
                if visit.button("🏠 I visited this place",
                                key=f"vis-{listing.listing_id}",
                                use_container_width=True):
                    _mark(store, listing.listing_id, "viewed")
                if unsave.button("Un-save", key=f"un-{listing.listing_id}",
                                 use_container_width=True):
                    _mark(store, listing.listing_id, "active")


def _scorecard(store: EventStore, listing: ListingState) -> None:
    with st.form(key=f"sc-{listing.listing_id}", border=True):
        st.markdown(_headline(listing))
        st.caption("60 seconds: how was it really? Skip anything you "
                   "didn't get a feel for.")
        verdict = st.radio("Would you take it?", ["pursue", "pass"],
                           format_func=lambda v: ("Yes — I want this place"
                                                  if v == "pursue"
                                                  else "No — not for me"),
                           horizontal=True, key=f"v-{listing.listing_id}")
        ratings: dict[str, int] = {}
        cols = st.columns(3)
        for i, (criterion, question) in enumerate(CRITERIA_QUESTIONS.items()):
            with cols[i % 3]:
                val = st.select_slider(
                    question, options=["skip", 1, 2, 3, 4, 5], value="skip",
                    key=f"r-{listing.listing_id}-{criterion}",
                    help="1 = terrible · 5 = amazing")
                if val != "skip":
                    ratings[criterion] = int(val)
        if st.form_submit_button("Save my impressions", type="primary"):
            store.append(scorecard_event(listing.listing_id, verdict,
                                         ratings, ts=_now_iso()))
            st.rerun()


def _tab_visited(store: EventStore, state) -> None:
    visited = [l for l in state.listings.values() if l.status == "viewed"]
    if not visited:
        st.info("After you tour a place, mark it \"I visited\" in Saved — "
                "then rate it here so Doma learns what you actually like.")
        return
    pending = [l for l in visited if l.scorecard is None]
    done = [l for l in visited if l.scorecard is not None]
    for listing in pending:
        _scorecard(store, listing)
    if done:
        st.markdown("#### Rated")
        for listing in done:
            verdict = listing.scorecard.get("verdict")
            icon = "✅ would take it" if verdict == "pursue" else "❌ passed"
            st.markdown(f"- {_headline(listing)} — {icon}")


def _tab_taste(store: EventStore, state) -> None:
    st.caption("What Doma believes matters to you. It only changes when "
               "you approve.")
    for criterion, weight in sorted(state.weights.items(),
                                    key=lambda kv: -kv[1]):
        name = criterion.replace("_", " ").title()
        st.markdown(f"- **{name}** — {weight:.0%} of every score")
    n_cards = sum(1 for l in state.listings.values() if l.scorecard)
    st.divider()
    proposal = propose_weights(state)
    if proposal is None:
        st.info(f"No changes to suggest yet ({n_cards} visit"
                f"{'s' if n_cards != 1 else ''} rated so far — Doma speaks "
                f"up once a criterion has {MIN_RATINGS}+ ratings).")
        return
    st.markdown("#### Doma noticed something")
    for criterion in state.weights:
        old, new = proposal.previous[criterion], proposal.weights[criterion]
        if abs(new - old) < 0.005:
            continue
        name = criterion.replace("_", " ")
        direction = ("matters more to you than assumed" if new > old
                     else "seems to matter less than assumed")
        ratings = proposal.evidence.get(criterion, {}).get("ratings")
        basis = f" (your ratings: {ratings})" if ratings else ""
        st.markdown(f"- **{name.title()}** {direction}: {old:.0%} → "
                    f"{new:.0%}{basis}")
    yes, no, _sp = st.columns([1, 1, 3])
    if yes.button("Yes, update my taste", type="primary"):
        store.append(weights_updated_event(proposal.weights,
                                           proposal.previous,
                                           proposal.evidence, ts=_now_iso()))
        st.success("Updated — run `./doma rescore` to re-rank everything.")
        st.rerun()
    if no.button("Not now"):
        st.caption("Okay — it'll keep learning.")


def _sidebar(state, db_path: str, store: EventStore) -> None:
    st.sidebar.title("🏠 Doma")
    st.sidebar.caption("Your apartment hunt, on autopilot. Doma scans "
                       "listings daily, scores them against your taste, and "
                       "flags the bait. You decide; it learns.")
    with st.sidebar.expander("Under the hood"):
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        active = sum(1 for l in state.listings.values()
                     if l.status == "active")
        st.markdown(
            f"- {len(state.listings)} listings tracked, {active} active\n"
            f"- {len(store.read_all())} events in the store\n"
            f"- RentCast scans: {state.scan_months.get(month, 0)}/40 "
            f"this month\n"
            f"- Last scan: {(state.last_scan_ts or 'never')[:16]}")
        if state.saturated:
            st.markdown("- Paused (no new inventory): "
                        + ", ".join(sorted(state.saturated)))
        st.caption(f"Event store: {db_path}")


def main() -> None:
    db_path = os.environ.get("DOMA_DB", "doma.db")
    if not Path(db_path).exists():
        st.title("🏠 Doma")
        st.info("No hunt data yet. Run `./doma run` in your terminal first — "
                "then refresh this page.")
        return
    store = EventStore(db_path)
    state = project(store.read_all())
    _sidebar(state, db_path, store)

    undecided = sorted(
        (l for l in state.listings.values()
         if l.status == "active" and l.score is not None),
        key=lambda l: (-(l.score or 0), -(l.score_confidence or 0),
                       l.price or 10**9))

    today, browse, saved, visited, taste = st.tabs(
        ["🌅 Today", "🔍 Browse", "♥ Saved", "🏠 Visited", "🎯 Your taste"])
    with today:
        _tab_today(store, undecided)
    with browse:
        _tab_browse(store, undecided)
    with saved:
        _tab_saved(store, state)
    with visited:
        _tab_visited(store, state)
    with taste:
        _tab_taste(store, state)


main()
