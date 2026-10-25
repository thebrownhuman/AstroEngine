"""KP significators reproduce Prokerala, Ascendant included.

Expected values are copied from Prokerala's kp-house-significator and
kp-planet-significator responses for Delhi, 1990-01-15 04:30, KP ayanamsa.
The comparison over eight births is validation/compare_coverage.py.
"""
from fastapi.testclient import TestClient

from astro_engine.api import app

client = TestClient(app)

KP = client.post("/v1/kp", json={
    "date": "1990-01-15", "time": "04:30", "latitude": 28.6139, "longitude": 77.2090,
    "timezone": "Asia/Kolkata", "ayanamsa": "krishnamurti", "prokerala_compatible": True,
}).json()


def _names(items):
    return [x["name"] for x in items]


def test_ascendant_is_a_point_between_saturn_and_rahu():
    names = [p["planet"]["name"] for p in KP["planets"]]
    assert names[6:9] == ["Saturn", "Ascendant", "Rahu"]
    ascendant = KP["planets"][7]
    assert ascendant["planet"]["id"] == 100
    assert ascendant["house"] == 1


def test_house_significators_list_the_ascendant_by_star():
    houses = {h["house"]["number"]: h for h in KP["house_significators"]}
    assert _names(houses[1]["cusp_nakshatra_occupants"]) == ["Mars", "Ascendant", "Rahu", "Ketu"]
    assert _names(houses[8]["cusp_owner_nakshatra_planets"]) == ["Mars", "Ascendant", "Ketu"]
    assert "Ascendant" not in _names(houses[1]["cusp_occupants"])


def test_planet_significators_four_levels():
    by_name = {p["planet"]["name"]: p for p in KP["planet_significators"]}
    moon = by_name["Moon"]
    assert moon["nakshatra_lord_house"]["number"] == 2
    assert moon["occupied_house"]["number"] == 9
    assert [h["number"] for h in moon["rasi_lord_house"]] == [7, 11, 12]
    assert [h["number"] for h in moon["rasi_lord_own_house"]] == [9]
    lagna = by_name["Ascendant"]
    assert lagna["planet"]["vedic_name"] == "Lagna"
    assert lagna["occupied_house"]["number"] == 1
    assert [h["number"] for h in lagna["rasi_lord_house"]] == [8, 10]
    assert lagna["rasi_lord_own_house"] == []
