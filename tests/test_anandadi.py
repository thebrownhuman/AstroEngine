"""Anandadi yoga matches Prokerala's anandadi-yoga.

Expected ids and windows are copied from their responses; boundaries get two
seconds because their Moon timings in the day endpoints scatter by about one.
"""
from datetime import datetime

from fastapi.testclient import TestClient

from astro_engine import anandadi
from astro_engine.api import app

client = TestClient(app)


def _yogas(date, lat, lon, zone):
    return client.post("/v1/muhurta", json={
        "date": date, "latitude": lat, "longitude": lon, "timezone": zone,
    }).json()["anandadi_yoga"]


def _near(ours, theirs):
    return abs((datetime.fromisoformat(ours) - datetime.fromisoformat(theirs)).total_seconds()) <= 2


def test_weekday_starts_four_stars_apart():
    # Monday counts from Mrigashira, so Purva Phalguni (10) is Dhwaja (6).
    assert anandadi.yoga_index(10, 1) == 6
    assert anandadi.yoga_index(0, 0) == 0
    assert anandadi.YOGAS[6][:2] == ("Dhwaja", "Soubhagya")


def test_abhijit_sits_between_uttara_ashadha_and_shravana():
    assert anandadi.star_of(276.0) == 20
    assert anandadi.star_of(278.0) == 21
    assert anandadi.star_of(281.0) == 22


def test_delhi_day_lists_both_nakshatras_until_next_sunrise():
    yogas = _yogas("1990-01-15", 28.6139, 77.2090, "Asia/Kolkata")
    assert [y["id"] for y in yogas] == [6, 7]
    assert _near(yogas[0]["start"], "1990-01-14T21:37:36")
    assert _near(yogas[1]["start"], "1990-01-15T23:03:23")
    assert _near(yogas[1]["end"], "1990-01-17T01:06:53")


def test_nakshatra_running_past_midnight_still_counts():
    # Buenos Aires, 1965-09-30: Kaal then Dhumra, which starts at 01:26 on Oct 1.
    yogas = _yogas("1965-09-30", -34.6037, -58.3816, "America/Argentina/Buenos_Aires")
    assert [y["name"] for y in yogas] == ["Kaal", "Dhumra"]
