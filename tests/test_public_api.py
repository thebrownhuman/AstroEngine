"""API key auth, per-key rate limiting and CORS for public exposure."""

import pytest
from fastapi.testclient import TestClient

from astro_engine import api


@pytest.fixture
def client(monkeypatch):
    def make(keys=None, limit=None, cors=None):
        for name, value in (("ASTRO_API_KEYS", keys), ("ASTRO_RATE_LIMIT", limit),
                            ("ASTRO_CORS_ORIGINS", cors)):
            if value is None:
                monkeypatch.delenv(name, raising=False)
            else:
                monkeypatch.setenv(name, value)
        return TestClient(api.create_app())
    yield make
    monkeypatch.undo()
    api.guard.configure()  # Leave later tests with the real environment.


def test_health_and_docs_open_with_auth_enabled(client):
    c = client(keys="secret")
    assert c.get("/health").status_code == 200
    assert c.get("/openapi.json").status_code == 200
    assert c.get("/docs").status_code == 200


def test_v1_requires_key(client):
    c = client(keys="secret,other")
    r = c.get("/v1/tool-definitions")
    assert r.status_code == 401
    assert r.json()["detail"]
    assert c.get("/v1/tool-definitions", headers={"X-API-Key": "wrong"}).status_code == 401


def test_v1_accepts_any_configured_key(client):
    c = client(keys="secret, other")
    assert c.get("/v1/tool-definitions", headers={"X-API-Key": "secret"}).status_code == 200
    assert c.get("/v1/tool-definitions", headers={"X-API-Key": "other"}).status_code == 200


def test_auth_disabled_when_env_unset(client):
    assert client().get("/v1/tool-definitions").status_code == 200
    assert client(keys=" , ").get("/v1/tool-definitions").status_code == 200


def test_rate_limit_per_key(client):
    c = client(keys="a,b", limit="3")
    for _ in range(3):
        assert c.get("/v1/tool-definitions", headers={"X-API-Key": "a"}).status_code == 200
    r = c.get("/v1/tool-definitions", headers={"X-API-Key": "a"})
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) >= 1
    # Separate bucket for another key.
    assert c.get("/v1/tool-definitions", headers={"X-API-Key": "b"}).status_code == 200


def test_rate_limit_falls_back_to_cf_ip(client):
    c = client(limit="1")
    assert c.get("/v1/tool-definitions", headers={"CF-Connecting-IP": "1.1.1.1"}).status_code == 200
    assert c.get("/v1/tool-definitions", headers={"CF-Connecting-IP": "1.1.1.1"}).status_code == 429
    assert c.get("/v1/tool-definitions", headers={"CF-Connecting-IP": "2.2.2.2"}).status_code == 200


def test_health_not_rate_limited(client):
    c = client(limit="1")
    for _ in range(3):
        assert c.get("/health").status_code == 200


def test_cors_off_by_default_and_on_when_configured(client):
    h = {"Origin": "https://shivanshmishra.in"}
    assert "access-control-allow-origin" not in client().get("/health", headers=h).headers
    r = client(cors="https://shivanshmishra.in").get("/health", headers=h)
    assert r.headers["access-control-allow-origin"] == "https://shivanshmishra.in"


def test_default_limit_is_60_with_auth_and_off_without(client):
    client(keys="k")
    assert api.guard.Guard.settings.rate_limit == 60
    client()
    assert api.guard.Guard.settings.rate_limit == 0
