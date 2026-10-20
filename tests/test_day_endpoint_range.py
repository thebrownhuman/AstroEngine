"""Calendar-day endpoints must refuse unsupported dates with a 422, not a 500.

/v1/chart and friends are protected by chart.build(). The day-level routes
(/v1/muhurta, /v1/bala) never go through it, so they need their own guard:
swisseph raises its own Error type beyond the ephemeris range, which is not a
ValueError and so used to surface as a bare Internal Server Error.
"""

import pytest
from fastapi.testclient import TestClient

from astro_engine.api import app

# raise_server_exceptions=False so an unhandled error shows up as the 500 a
# real client would receive, instead of re-raising inside the test.
client = TestClient(app, raise_server_exceptions=False)

PLACE = {"latitude": 28.6139, "longitude": 77.209, "timezone": "Asia/Kolkata"}


@pytest.mark.parametrize("path", ["/v1/muhurta", "/v1/bala"])
@pytest.mark.parametrize("year", ["3500", "5000", "9000"])
def test_day_endpoints_reject_dates_beyond_the_ephemeris(path, year):
    response = client.post(path, json={**PLACE, "date": f"{year}-06-15"})
    assert response.status_code == 422, response.text
    assert "detail" in response.json()


@pytest.mark.parametrize("path", ["/v1/muhurta", "/v1/bala"])
def test_day_endpoints_still_serve_ordinary_dates(path):
    response = client.post(path, json={**PLACE, "date": "1990-01-15"})
    assert response.status_code == 200, response.text


def test_bala_personal_branch_is_guarded_too():
    """The for_person branch computes the Moon outside the first try block."""
    response = client.post("/v1/bala", json={
        **PLACE, "date": "5000-06-15", "janma_nakshatra": 3, "janma_rasi": 1,
    })
    assert response.status_code == 422, response.text
