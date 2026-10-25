"""Yearly chandrashtama matches Prokerala's chandrashtama-periods.

Expected values are copied from their response for Delhi, 1990-01-15 04:30,
year 2026; boundaries get two seconds.
"""
from datetime import datetime

from fastapi.testclient import TestClient

from astro_engine.api import app

client = TestClient(app)

YEAR = client.post("/v1/chandrashtama", json={
    "date": "1990-01-15", "time": "04:30", "latitude": 28.6139, "longitude": 77.2090,
    "timezone": "Asia/Kolkata", "prokerala_compatible": True, "year": 2026,
}).json()


def _near(ours, theirs):
    return abs((datetime.fromisoformat(ours) - datetime.fromisoformat(theirs)).total_seconds()) <= 2


def test_eighth_from_simha_is_meena():
    assert YEAR["rasi"]["name"] == "Meena"
    assert [n["index"] for n in YEAR["nakshatras"]] == [24, 25, 26]


def test_thirteen_periods_with_uttara_bhadrapada_peak():
    periods = YEAR["periods"]
    assert len(periods) == 13
    first = periods[0]
    assert _near(first["start"], "2026-01-23T08:33:38")
    assert _near(first["end"], "2026-01-25T13:35:46")
    stars = first["nakshatra_timings"]
    assert [s["is_peak"] for s in stars] == [False, True, False]
    assert _near(stars[1]["start"], "2026-01-23T14:32:59")


def test_no_peak_when_the_sixteenth_star_is_outside_the_sign():
    # Reykjavik 1972, janma Chitra (13) in Tula: the eighth is Vrishabha
    # (Krittika to Mrigashira), and the sixteenth star, Bharani (1), is not in it.
    year = client.post("/v1/chandrashtama", json={
        "date": "1972-06-21", "time": "00:05", "latitude": 64.1466,
        "longitude": -21.9426, "timezone": "Atlantic/Reykjavik", "year": 2026,
        "prokerala_compatible": True,
    }).json()
    assert year["peak_nakshatra"] is None
    assert not any(s["is_peak"] for p in year["periods"] for s in p["nakshatra_timings"])
