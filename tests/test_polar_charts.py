"""Charts at Arctic latitudes: sunrise- and cusp-dependent blocks degrade to
null with a warning instead of rejecting the whole chart."""
from datetime import date, timedelta

import pytest

from astro_engine.chart import BirthData, build


def _chart(day, lat, lon, tz, **kw):
    return build(BirthData(day.year, day.month, day.day, 10, 30, 0, lat, lon, tz), **kw)


@pytest.mark.parametrize("day", [date(1990, 3, 1), date(1990, 10, 15)])
def test_twilight_window_at_78n_returns_chart(day):
    chart = _chart(day, 78.2, 15.6, "Arctic/Longyearbyen")
    assert chart["lagna"]["sign_en"]
    assert chart["cusps"] is None
    assert any("cusps" in w for w in chart["warnings"])


def test_polar_night_nulls_sunrise_blocks():
    chart = _chart(date(1990, 1, 15), 78.2, 15.6, "Arctic/Longyearbyen",
                   include_upagrahas=True)
    assert chart["panchanga"] is None and chart["solar_day"] is None
    assert chart["upagrahas"] is None
    assert any("no solar" in w for w in chart["warnings"])
    assert chart["dasha"] and chart["grahas"]


@pytest.mark.parametrize("lat,lon,tz", [
    (78.2, 15.6, "Arctic/Longyearbyen"), (70.0, 25.0, "Europe/Oslo"),
])
def test_year_sweep_never_raises(lat, lon, tz):
    day = date(1990, 1, 1)
    while day.year == 1990:
        chart = _chart(day, lat, lon, tz)
        assert chart["lagna"]
        if chart["solar_day"] is None:
            assert chart["warnings"]
        day += timedelta(days=9)


def test_ordinary_chart_has_no_warnings():
    chart = _chart(date(1990, 5, 5), 28.6, 77.2, "Asia/Kolkata")
    assert "warnings" not in chart and chart["cusps"]


def test_timezone_source_place(monkeypatch):
    from fastapi.testclient import TestClient
    from astro_engine import api
    from astro_engine.api import app
    from astro_engine.places import Place

    fake = Place(name="Delhi", admin1="Delhi", country="India", country_code="IN", latitude=28.6,
                 longitude=77.2, timezone="Asia/Kolkata", population=1)
    monkeypatch.setattr(api, "resolve", lambda *a, **k: fake)
    body = TestClient(app).post("/v1/chart", json={
        "date": "1990-05-05", "time": "10:30", "place": "Delhi"}).json()
    assert body["input"]["timezone_source"] == "place"
    body = TestClient(app).post("/v1/chart", json={
        "date": "1990-05-05", "time": "10:30", "latitude": 28.6, "longitude": 77.2,
        "timezone": "Asia/Kolkata"}).json()
    assert body["input"]["timezone_source"] == "explicit"


def test_summary_survives_missing_panchanga():
    from astro_engine.chart import summarise
    chart = _chart(date(1990, 1, 15), 78.2, 15.6, "Arctic/Longyearbyen")
    assert "unavailable" in summarise(chart)
