"""Outreach drafting: the LLM writes, deterministic guardrails own the truth.

The draft may only contain facts we verified; every number in the output is
checked against the listing's known values, and claims about unknown facts
(fee) are banned. A dishonest or failed generation falls back to a
deterministic template. Nothing is ever sent — drafts await human approval.
"""
from __future__ import annotations

import re
from typing import Any, Callable

import requests

from doma.state import ListingState

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DRAFT_MODEL = "anthropic/claude-haiku-4.5"

_SYSTEM = (
    "You draft a short, warm, specific apartment-inquiry message on behalf "
    "of a renter. HARD RULES: use ONLY the facts provided; if a fact is "
    "marked unknown, you may ASK about it but never assert it; do not "
    "invent numbers, amenities, or availability; no subject line; sign off "
    "with '[Your name]'. Keep it under 120 words."
)


def _known_facts(listing: ListingState) -> dict[str, Any]:
    facts: dict[str, Any] = {
        "address": listing.address,
        "unit": listing.unit,
        "neighborhood": listing.neighborhood,
        "price_per_month": listing.price,
    }
    facts["fee"] = ("no fee" if listing.fee is False
                    else "fee" if listing.fee else "unknown")
    facts["laundry"] = "unknown"
    return facts


def build_prompt(listing: ListingState) -> str:
    """The user message: verified facts + what is unknown."""
    facts = _known_facts(listing)
    lines = [f"- {k}: {v if v is not None else 'unknown'}"
             for k, v in facts.items()]
    return ("Draft an inquiry for this listing. Facts (anything 'unknown' "
            "may only be asked about):\n" + "\n".join(lines))


def _allowed_numbers(listing: ListingState) -> set[str]:
    allowed: set[str] = set()
    for value in (listing.price, listing.address, listing.unit,
                  listing.neighborhood, listing.zip):
        for token in re.findall(r"\d+", str(value or "")):
            allowed.add(token)
    if listing.price is not None:
        allowed.add(f"{listing.price:,}".replace(",", ""))
    return allowed


def validate_draft(draft: str, listing: ListingState) -> list[str]:
    """Every violation of the honesty rules found in a draft."""
    violations: list[str] = []
    allowed = _allowed_numbers(listing)
    for token in re.findall(r"\d[\d,]*", draft):
        if token.replace(",", "") not in allowed:
            violations.append(f"unverified number in draft: {token}")
    if listing.fee is not False and re.search(r"no[- ]fee", draft, re.I):
        violations.append("claims 'no fee' but fee is unknown/true")
    return violations


def fallback_draft(listing: ListingState) -> str:
    """Deterministic template: honest by construction."""
    unit = f" (unit {listing.unit})" if listing.unit else ""
    price = f" listed at ${listing.price:,}/month" if listing.price else ""
    return (f"Hello! I came across the listing at {listing.address}{unit}"
            f"{price} and I'm very interested. Is it still available? "
            f"Could you tell me about the broker fee, laundry, and which "
            f"way the unit faces? I'd love to schedule a viewing this week. "
            f"Thank you!\n\n[Your name]")


def draft_outreach(api_key: str, listing: ListingState,
                   post: Callable[..., Any] = requests.post
                   ) -> tuple[str, str]:
    """One draft: (text, generation_method). Falls back on failure or
    dishonesty — the fallback is always safe to show."""
    try:
        response = post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": DRAFT_MODEL,
                  "messages": [{"role": "system", "content": _SYSTEM},
                               {"role": "user",
                                "content": build_prompt(listing)}],
                  "temperature": 0.4, "max_tokens": 400},
            timeout=60,
        )
        response.raise_for_status()
        draft = response.json()["choices"][0]["message"]["content"].strip()
    except Exception:  # any failure -> deterministic fallback, never a crash
        return fallback_draft(listing), "fallback"
    if not draft or validate_draft(draft, listing):
        return fallback_draft(listing), "fallback"
    return draft, "openrouter_api"
