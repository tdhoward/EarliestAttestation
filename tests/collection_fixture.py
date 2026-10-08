"""Bounded 25-witness pilot for regression tests, independent of live collection growth."""
from pathlib import Path

from build_collection import DATA, build_data, read_json

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PILOT_DATA = FIXTURES / "explorer-pilot.v4.json"


def pilot_collection():
    return read_json(FIXTURES / "collection-pilot.json")["collection"]


def pilot_discovery():
    return read_json(FIXTURES / "collection-pilot.json")["discovery"]


def build_pilot(collection=None, *, discovery_records=None):
    return build_data(pilot_collection() if collection is None else collection, DATA,
                      discovery_records=pilot_discovery() if discovery_records is None else discovery_records)
