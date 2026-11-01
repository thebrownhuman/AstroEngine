"""Every input-validation failure keeps its own status and message.

The exception mapping in `build` is shared by all chart routes, so these pin
that a polar fix cannot turn a specific 4xx into a generic one (or a 200).
"""
import pytest
from fastapi.testclient import TestClient

from astro_engine import api
from astro_engine.api import app

client = TestClient(app)
OK = {"date": "1990-05-05", "time": "10:30", "latitude": 28.6,
      "longitude": 77.2, "timezone": "Asia/Kolkata"}
POLAR = {"latitude": 78.2232, "longitude": 15.6469, "timezone": "Arctic/Longyearbyen"}


def _post(path="/v1/chart", **overrides):
    body = {**OK, **overrides}
    return client.post(path, json={k: v for k, v in body.items() if v is not None})


@pytest.mark.parametrize("overrides,needle", [
    ({"date": "0005-01-01"}, "birth year must be between 21 and 3000"),
    ({"date": "3500-01-01"}, "birth year must be between 21 and 3000"),
    ({"date": "1990-13-45"}, "could not parse date/time: month must be in 1..12"),
    ({"time": "25:99"}, "could not parse date/time: hour must be in 0..23"),
    ({"latitude": 95}, "less than or equal to 90"),
    ({"longitude": 200}, "less than or equal to 180"),
    ({"ayanamsa": "nope"}, "unknown ayanamsa 'nope'"),
    ({"timezone": "Not/AZone"}, "unknown IANA timezone 'Not/AZone'"),
    ({"latitude": None, "longitude": None}, "supply either `place`"),
])
def test_validation_errors_keep_their_message(overrides, needle):
    response = _post(**overrides)
    assert response.status_code == 422
    assert needle in response.text


def test_year_message_is_only_for_year_errors():
    for overrides in ({"ayanamsa": "nope"}, {"timezone": "Not/AZone"}, {"time": "25:99"}):
        assert "birth year" not in _post(**overrides).text


def test_unknown_place_is_a_422(monkeypatch):
    def missing(*args, **kwargs):
        raise ValueError("no place matching 'Zzzzqqxx'")
    monkeypatch.setattr(api, "resolve", missing)
    response = _post(latitude=None, longitude=None, timezone=None, place="Zzzzqqxx")
    assert response.status_code == 422
    assert "Zzzzqqxx" in response.text


@pytest.mark.parametrize("day", ["2020-06-21", "2020-12-21"])
def test_polar_day_and_night_chart_is_200_with_warning(day):
    response = _post(date=day, **POLAR)
    assert response.status_code == 200
    body = response.json()
    assert body["panchanga"] is None and body["solar_day"] is None
    assert any("no solar" in w for w in body["warnings"])


def test_polar_upagrahas_is_a_clear_422():
    response = _post("/v1/upagrahas", date="2020-12-21", **POLAR)
    assert response.status_code == 422
    assert "no solar rise exists" in response.text


def test_polar_kp_is_a_clear_422():
    response = _post("/v1/kp", date="1990-03-01", latitude=78.2, longitude=15.6,
                     timezone="Arctic/Longyearbyen")
    assert response.status_code == 422
    assert "Placidus" in response.text
