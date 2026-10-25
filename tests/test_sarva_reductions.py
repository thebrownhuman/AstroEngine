"""Sarvashtakavarga trikona and ekaadhipatya reproduce Prokerala.

Prokerala builds the two reduced sarva tables differently from its own
per-graha tables (measured 7/7 births in validation/compare_coverage.py):

  trikona       sum over grahas of the trinal reduction *without* the
                zero-in-a-trine rule
  ekaadhipatya  sum over grahas of the same-lord reduction on the raw
                prastara, with Rahu, Ketu and the lagna counted as occupants

Expected house scores are copied from Prokerala for Delhi 1990-01-15 04:30.
"""
from fastapi.testclient import TestClient

from astro_engine.api import app

client = TestClient(app)


def _sarva(date, time, lat, lon, zone):
    return client.post("/v1/ashtakavarga", json={
        "date": date, "time": time, "latitude": lat, "longitude": lon,
        "timezone": zone, "prokerala_compatible": True,
    }).json()["sarvashtakavarga"]


def _scores(stage):
    return [h["score"] for h in stage["houses"]]


def test_delhi_reduced_sarva_tables():
    s = _sarva("1990-01-15", "04:30", 28.6139, 77.2090, "Asia/Kolkata")
    assert _scores(s["trikona"]) == [18, 1, 4, 10, 9, 12, 6, 8, 6, 10, 14, 14]
    assert s["trikona"]["score"] == 112
    assert _scores(s["ekaadhipatya"]) == [32, 23, 25, 17, 10, 20, 17, 26, 20, 32, 21, 17]
    assert s["ekaadhipatya"]["score"] == 260


def test_lagna_counts_as_occupied_for_sarva_ekaadhipatya():
    # Sydney 1956: lagna in Mesha with no graha there; Prokerala leaves the
    # first house at 23 rather than levelling it to 8.
    s = _sarva("1956-01-15", "14:10", -33.8688, 151.2093, "Australia/Sydney")
    assert _scores(s["ekaadhipatya"])[0] == 23
