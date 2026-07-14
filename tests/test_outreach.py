from doma.outreach import (build_prompt, draft_outreach, fallback_draft,
                           validate_draft)
from doma.state import ListingState


def _listing(**kw) -> ListingState:
    base = dict(listing_id="x", source="streeteasy_email",
                neighborhood="mott haven", price=2595, status="pursuing",
                first_seen_ts="2026-07-13T09:00:00+00:00",
                last_seen_ts="2026-07-13T09:00:00+00:00",
                address="224 East 135th Street", unit="2116S", fee=None)
    base.update(kw)
    return ListingState(**base)


def test_prompt_contains_facts_and_unknown_rules() -> None:
    prompt = build_prompt(_listing())
    assert "224 East 135th Street" in prompt
    assert "2595" in prompt or "2,595" in prompt
    assert "unknown" in prompt.lower()  # instructs asking, not asserting


def test_validate_flags_fabricated_numbers() -> None:
    ok = "Hi, I'm interested in 224 East 135th Street #2116S at $2,595."
    assert validate_draft(ok, _listing()) == []
    fabricated = "It has 900 square feet and costs $2,400."
    violations = validate_draft(fabricated, _listing())
    assert any("900" in v for v in violations)
    assert any("2400" in v or "2,400" in v for v in violations)


def test_validate_flags_no_fee_claim_when_unknown() -> None:
    draft = "Great that it's no fee! Is it available?"
    assert any("fee" in v for v in validate_draft(draft, _listing(fee=None)))
    assert validate_draft(draft, _listing(fee=False)) == []


def test_fallback_draft_is_honest() -> None:
    draft = fallback_draft(_listing())
    assert validate_draft(draft, _listing()) == []
    assert "224 East 135th Street" in draft


def test_draft_outreach_falls_back_on_api_failure() -> None:
    def broken_post(*a, **kw):
        raise RuntimeError("api down")
    draft, method = draft_outreach("key", _listing(), post=broken_post)
    assert method == "fallback"
    assert validate_draft(draft, _listing()) == []


def test_draft_outreach_falls_back_on_dishonest_output() -> None:
    class FakeResponse:
        def raise_for_status(self): pass
        def json(self):
            return {"choices": [{"message": {"content":
                    "This 900 sqft no fee gem!"}}]}
    draft, method = draft_outreach("key", _listing(),
                                   post=lambda *a, **kw: FakeResponse())
    assert method == "fallback"


def test_draft_outreach_accepts_honest_output() -> None:
    class FakeResponse:
        def raise_for_status(self): pass
        def json(self):
            return {"choices": [{"message": {"content":
                    "Hello! Is 224 East 135th Street unit 2116S at $2,595 "
                    "still available? Could you tell me about the fee and "
                    "laundry? I'd love to schedule a viewing."}}]}
    draft, method = draft_outreach("key", _listing(),
                                   post=lambda *a, **kw: FakeResponse())
    assert method == "openrouter_api"
    assert "2116S" in draft
