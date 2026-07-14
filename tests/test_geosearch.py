from doma.adapters.geosearch import to_geo

# Canned response shape verified live 2026-07-15 against
# geosearch.planninglabs.nyc/v2/search (Pelias).
PELIAS = {"features": [{
    "geometry": {"coordinates": [-73.931046, 40.809945]},
    "properties": {"postalcode": "10451", "borough": "Bronx",
                   "confidence": 0.8, "name": "224 EAST 135 STREET"},
}]}


def test_to_geo_extracts_verified_fields() -> None:
    geo = to_geo(PELIAS)
    assert geo == {"zip": "10451", "borough": "Bronx",
                   "lat": 40.809945, "lon": -73.931046,
                   "confidence": 0.8}


def test_low_confidence_or_empty_is_none() -> None:
    low = {"features": [{"geometry": {"coordinates": [0, 0]},
                         "properties": {"postalcode": "10451",
                                        "confidence": 0.4}}]}
    assert to_geo(low) is None
    assert to_geo({"features": []}) is None
    # No postalcode -> useless for enrichment -> None, never guessed.
    nozip = {"features": [{"geometry": {"coordinates": [0, 0]},
                           "properties": {"confidence": 0.9}}]}
    assert to_geo(nozip) is None
