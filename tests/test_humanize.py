from doma.humanize import (building_label, fee_label, fit_label,
                           knowledge_label, walk_label)


def test_fit_labels() -> None:
    assert fit_label(0.9) == "Strong fit"
    assert fit_label(0.7) == "Good fit"
    assert fit_label(0.5) == "Fair fit"
    assert fit_label(0.2) == "Weak fit"
    assert fit_label(None) == "Not assessed yet"


def test_knowledge_labels() -> None:
    assert "little" in knowledge_label(0.2)
    assert "some" in knowledge_label(0.5)
    assert "a lot" in knowledge_label(0.8)


def test_walk_label_minutes() -> None:
    assert walk_label({"station": "Nassau Av", "walk_meters": 393}) == \
        "≈5 min walk to Nassau Av"
    assert walk_label(None) is None


def test_building_label_honesty() -> None:
    # Unmatched/unknown -> None (silence), never false reassurance.
    assert building_label({"total": 0, "matched": False}) is None
    assert building_label(None) is None
    assert building_label({"total": 3, "class_c": 1, "matched": True}) == \
        "3 open violations (1 serious)"
    assert building_label({"total": 0, "matched": True}) == \
        "clean building record"


def test_fee_label() -> None:
    assert fee_label(False) == "no broker fee"
    assert fee_label(None) is None
