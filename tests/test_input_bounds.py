"""Unauthenticated input must be bounded; out-of-range values get FastAPI's 422."""
import pytest
from fastapi.testclient import TestClient

from astro_engine import places
from astro_engine.api import ChartRequest, app
from astro_engine.vargas import VARGAS

client = TestClient(app)
CHART = {"date": "1990-01-15", "time": "04:30", "latitude": 28.6, "longitude": 77.2,
         "timezone": "Asia/Kolkata"}
needs_index = pytest.mark.skipif(
    not places.INDEX_PATH.exists(),
    reason="place index not built; run python -m astro_engine.places build",
)
NUM = {"first_name": "John", "last_name": "Doe", "date_of_birth": "2004-02-12"}


@needs_index
def test_places_limit_bounds():
    assert client.get("/v1/places", params={"q": "delhi", "limit": 50}).status_code == 200
    assert client.get("/v1/places", params={"q": "delhi", "limit": 1}).status_code == 200
    assert client.get("/v1/places", params={"q": "delhi", "limit": 51}).status_code == 422
    assert client.get("/v1/places", params={"q": "delhi", "limit": 0}).status_code == 422


@needs_index
def test_places_query_and_country_bounds():
    assert client.get("/v1/places", params={"q": "a" * 100}).status_code == 200
    assert client.get("/v1/places", params={"q": "a" * 101}).status_code == 422
    assert client.get("/v1/places", params={"q": ""}).status_code == 422
    assert client.get("/v1/places", params={"q": "x", "country": "I" * 100}).status_code == 200
    assert client.get("/v1/places", params={"q": "x", "country": "I" * 101}).status_code == 422


@pytest.mark.parametrize("field", ["first_name", "middle_name", "last_name"])
def test_numerology_name_bounds(field):
    assert client.post("/v1/numerology", json={**NUM, field: "a" * 100}).status_code == 200
    assert client.post("/v1/numerology", json={**NUM, field: "a" * 101}).status_code == 422


def test_numerology_date_bounds():
    assert client.post("/v1/numerology", json={**NUM, "date_of_birth": "2" * 33}).status_code == 422
    assert client.post("/v1/numerology", json={**NUM, "reference_date": "2" * 33}).status_code == 422


def test_vargas_rejects_overlong_and_duplicates():
    assert client.post("/v1/chart", json={**CHART, "vargas": ["D1"]}).status_code == 200
    r = client.post("/v1/chart", json={**CHART, "vargas": list(VARGAS) + ["D1"]})
    assert r.status_code == 422
    r = client.post("/v1/chart", json={**CHART, "vargas": ["D1", "D9", "D1"]})
    assert r.status_code == 422
    assert "duplicate" in r.text
    assert client.post("/v1/chart", json={**CHART, "vargas": ["D1"] * 5000}).status_code == 422


def test_all_vargas_exactly_at_limit_validates():
    assert len(ChartRequest(**CHART, vargas=list(VARGAS)).vargas) == len(VARGAS)


def test_chart_free_text_bounds():
    assert client.post("/v1/chart", json={**CHART, "timezone": "A" * 65}).status_code == 422
    r = client.post("/v1/chart", json={"date": "1990-01-15", "time": "04:30", "place": "D" * 201})
    assert r.status_code == 422
    assert client.post("/v1/chart", json={**CHART, "date": "1" * 33}).status_code == 422
    assert client.post("/v1/chart", json={**CHART, "ayanamsa": "l" * 65}).status_code == 422


def test_match_reuses_chart_bounds():
    boy = {**CHART, "vargas": ["D1", "D1"]}
    assert client.post("/v1/matching", json={"boy": boy, "girl": CHART}).status_code == 422
