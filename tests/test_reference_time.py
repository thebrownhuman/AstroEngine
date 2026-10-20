"""Default reference time must be "now" in the BIRTH location's local clock."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from astro_engine.api import app
from astro_engine.chart import BirthData, build

client = TestClient(app)

ZONES = [
    ("Asia/Kolkata", 28.6139, 77.209),
    ("America/Los_Angeles", 34.05, -118.25),
    ("Pacific/Auckland", -36.85, 174.76),
]


def _birth(tz, lat, lon):
    return {"date": "1990-01-15", "time": "04:30", "latitude": lat,
            "longitude": lon, "timezone": tz}


def _close(as_of, tz):
    expected = datetime.now(ZoneInfo(tz)).replace(tzinfo=None)
    return abs(datetime.fromisoformat(as_of) - expected) < timedelta(seconds=10)


@pytest.mark.parametrize("tz,lat,lon", ZONES)
def test_build_default_now_is_birth_local(tz, lat, lon):
    chart = build(BirthData(1990, 1, 15, 4, 30, 0, lat, lon, tz),
                  include_transits=True)
    assert _close(chart["current_dasha"]["as_of"], tz)
    assert _close(chart["transits"]["as_of"], tz)


@pytest.mark.parametrize("tz,lat,lon", ZONES)
def test_transits_endpoint_default_now_is_birth_local(tz, lat, lon):
    body = client.post("/v1/transits", json=_birth(tz, lat, lon)).json()
    assert _close(body["transits"]["as_of"], tz)


def test_explicit_aware_and_naive_unchanged():
    birth = BirthData(1990, 1, 15, 4, 30, 0, 28.6139, 77.209, "Asia/Kolkata")
    aware = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)
    c = build(birth, reference_time=aware)
    assert c["current_dasha"]["as_of"] == "2025-06-01T17:30:00"
    c = build(birth, reference_time=datetime(2025, 6, 1, 12, 0))
    assert c["current_dasha"]["as_of"] == "2025-06-01T12:00:00"
