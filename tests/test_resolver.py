from doma.resolver import identity_key, normalize_street


def test_normalize_street_expands_abbreviations() -> None:
    assert normalize_street("1208 Clay Ave") == "1208 clay avenue"
    assert normalize_street("240 E 10th St") == "240 east 10th street"
    assert normalize_street("55 N. 5th Blvd.") == "55 north 5th boulevard"


def test_normalize_street_collapses_noise() -> None:
    assert normalize_street("  1208   CLAY  AVENUE ") == "1208 clay avenue"
    assert normalize_street("1208 Clay Ave,") == "1208 clay avenue"


def test_identity_key_same_unit_same_key() -> None:
    a = identity_key("1208 Clay Ave", "4N")
    b = identity_key("1208 CLAY AVENUE", "4n")
    assert a == b == "1208-clay-avenue::4n"


def test_identity_key_strips_unit_prefixes() -> None:
    # RentCast says "Apt 4N", StreetEasy says "#4N" — same apartment.
    a = identity_key("1208 Clay Ave", "Apt 4N")
    b = identity_key("1208 Clay Ave", "#4N")
    c = identity_key("1208 Clay Ave", "Unit 4N")
    assert a == b == c == "1208-clay-avenue::4n"


def test_identity_key_unknown_unit_uses_fallback() -> None:
    # Two unit-less listings at the same address must NOT merge.
    a = identity_key("1208 Clay Ave", None, fallback="rentcast:rc-1")
    b = identity_key("1208 Clay Ave", None, fallback="rentcast:rc-2")
    assert a != b
    assert a == "1208-clay-avenue::rentcast:rc-1"
