"""Auspicious yogas match Prokerala's auspicious-yoga.

Expected periods are copied from their responses; boundaries get two seconds.
"""
from datetime import datetime

from fastapi.testclient import TestClient

from astro_engine.api import app

client = TestClient(app)


def _yogas(date, lat, lon, zone):
    rows = client.post("/v1/muhurta", json={
        "date": date, "latitude": lat, "longitude": lon, "timezone": zone,
    }).json()["auspicious_yoga"]
    return {row["name"]: row["period"] for row in rows}


def _near(ours, theirs):
    return abs((datetime.fromisoformat(ours) - datetime.fromisoformat(theirs)).total_seconds()) <= 2


def test_dwipushkar_sunday_dhanishta_dwitiya():
    yogas = _yogas("1956-01-15", -33.8688, 151.2093, "Australia/Sydney")
    (period,) = yogas["Dwipushkar"]
    assert [c["name"] for c in period["combination"]] == ["Dhanishta", "Dwitiya", "Sunday"]
    assert _near(period["start"], "1956-01-15T14:23:05")
    assert _near(period["end"], "1956-01-15T17:27:27")
    # Saturday's Shravana before Sunday's sunrise belongs to the day before.
    assert yogas["Sarvartha Siddhi"] == []


def test_next_mornings_combination_counts_until_its_nakshatra_ends():
    # Sunday 2010-03-21: Monday-with-Rohini begins at Monday's sunrise and is
    # listed; Monday-with-Mrigashira, in the next nakshatra, is not.
    yogas = _yogas("2010-03-21", -33.9249, 18.4241, "Africa/Johannesburg")
    (period,) = yogas["Sarvartha Siddhi"]
    assert [c["name"] for c in period["combination"]] == ["Rohini", "Monday"]
    assert _near(period["end"], "2010-03-22T09:50:14")
    assert yogas["Amrit Siddhi"] == []
