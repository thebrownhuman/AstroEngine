"""prokerala_compatible dasha timestamps reproduce Prokerala to the second.

Prokerala rounds the cycle start up to a whole second, truncates every
sub-period's length to whole seconds, and reports each end one second before
the next start. Measured on 5832 pratyantardashas over eight births; the
expected strings below are copied from their dasha-periods responses.
"""
from fastapi.testclient import TestClient

from astro_engine.api import app

client = TestClient(app)


def _dasha(date, time, lat, lon, zone, compatible=True):
    return client.post("/v1/chart", json={
        "date": date, "time": time, "latitude": lat, "longitude": lon,
        "timezone": zone, "vargas": ["D1"], "dasha_depth": 3,
        "prokerala_compatible": compatible,
    }).json()["dasha"]["mahadashas"]


def _find(periods, *lords):
    for lord in lords:
        periods = next(p for p in periods if p["lord"] == lord)
        last = periods
        periods = periods.get("sub_periods", [])
    return last


def test_cycle_start_rounds_up_to_whole_second():
    maha = _dasha("1988-11-02", "23:20", 51.5074, -0.1278, "Europe/London")
    assert maha[0]["start"] == "1986-09-30T12:05:44"
    assert maha[0]["end"] == "1993-09-30T06:05:43"
    assert maha[1]["sub_periods"][1]["start"] == "1997-01-29T18:05:44"


def test_pratyantar_lengths_are_truncated_and_accumulated():
    maha = _dasha("1990-01-15", "04:30", 28.6139, 77.2090, "Asia/Kolkata")
    assert _find(maha, "Mars", "Mars", "Saturn")["end"] == "2020-10-13T11:51:52"
    assert _find(maha, "Mars", "Mars", "Ketu")["start"] == "2020-11-03T14:57:12"
    assert _find(maha, "Venus")["end"] == "2004-07-30T22:08:23"


def test_default_mode_keeps_exact_boundaries():
    maha = _dasha("1988-11-02", "23:20", 51.5074, -0.1278, "Europe/London",
                  compatible=False)
    assert maha[0]["end"] == maha[1]["start"]
