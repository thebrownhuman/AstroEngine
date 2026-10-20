"""Edges of the supported date range: 422 outside it, truthful ephemeris inside."""

import pytest
from fastapi.testclient import TestClient

from astro_engine.api import app
from astro_engine.ephemeris import MAX_YEAR, MIN_YEAR

client = TestClient(app)


def _post(year, path="/v1/chart", month=1, day=1):
    return client.post(path, json={
        "date": f"{year:04d}-{month:02d}-{day:02d}", "time": "12:00",
        "latitude": 28.6, "longitude": 77.2, "timezone": "Asia/Kolkata",
    })


@pytest.mark.parametrize("year", [1, 5, MIN_YEAR - 1, MAX_YEAR + 1, 3003, 5000])
@pytest.mark.parametrize("path", ["/v1/chart", "/v1/chart/summary", "/v1/kp"])
def test_out_of_range_is_422_naming_the_range(year, path):
    r = _post(year, path)
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    assert str(MIN_YEAR) in detail and str(MAX_YEAR) in detail


@pytest.mark.parametrize("year,month,day", [
    (MIN_YEAR, 1, 1), (MIN_YEAR, 3, 7), (MIN_YEAR, 6, 15), (MIN_YEAR, 12, 31),
    (MAX_YEAR, 1, 1), (MAX_YEAR, 12, 31),
])
def test_boundary_years_still_work(year, month, day):
    r = _post(year, month=month, day=day)
    assert r.status_code == 200, r.text


@pytest.mark.parametrize("year", [1900, 1990, 2024, 2399])
def test_in_range_reports_swieph(year):
    engine = _post(year).json()["engine"]
    assert engine["ephemeris"] == "swieph"
    assert "ephemeris_note" not in engine


@pytest.mark.parametrize("year", [1500, 2600])
def test_outside_bundled_files_reports_moshier(year):
    engine = _post(year).json()["engine"]
    assert engine["ephemeris"] == "moshier"
    assert "arcsecond" in engine["ephemeris_note"]


def test_health_reports_file_coverage_and_keeps_backend():
    h = client.get("/health").json()
    assert h["ephemeris"] == "swieph"
    assert h["ephemeris_coverage"] == {"from_year": 1800, "to_year": 2400}
    assert h["supported_years"] == {"from_year": MIN_YEAR, "to_year": MAX_YEAR}
