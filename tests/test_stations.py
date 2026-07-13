import json
from pathlib import Path

from doma.adapters.stations import Station, load_stations, nearest_station

FIXTURE = Path(__file__).parent / "fixtures" / "stations_sample.json"


def test_load_stations_parses_fixture() -> None:
    stations = load_stations(FIXTURE)
    assert len(stations) > 100
    first = stations[0]
    assert isinstance(first, Station)
    assert first.lat != 0.0 and first.lon != 0.0
    assert isinstance(first.routes, frozenset)


def test_nearest_station_finds_closest() -> None:
    stations = [
        Station(name="Near", routes=frozenset({"G"}), lat=40.7240, lon=-73.9510),
        Station(name="Far", routes=frozenset({"G"}), lat=40.8000, lon=-73.9000),
    ]
    station, meters = nearest_station(40.7237, -73.9509, stations)
    assert station.name == "Near"
    assert meters < 100


def test_nearest_station_filters_by_route() -> None:
    stations = [
        Station(name="G stop", routes=frozenset({"G"}), lat=40.7240, lon=-73.9510),
        Station(name="L stop", routes=frozenset({"L"}), lat=40.7100, lon=-73.9400),
    ]
    station, _ = nearest_station(40.7237, -73.9509, stations,
                                 routes=frozenset({"L"}))
    assert station.name == "L stop"


def test_nearest_station_no_serving_station_raises() -> None:
    stations = [
        Station(name="G stop", routes=frozenset({"G"}), lat=40.7240, lon=-73.9510),
    ]
    try:
        nearest_station(40.7237, -73.9509, stations, routes=frozenset({"Z"}))
    except ValueError as exc:
        assert "Z" in str(exc)
    else:
        raise AssertionError("expected ValueError for unserved route")
