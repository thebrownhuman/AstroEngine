"""Cached client for VedIntel AstroAPI, a second, independent reference.

Prokerala is what the engine reproduces; VedIntel is a separate provider used
to cross-check it. Where all three agree the number is very likely right;
where only Prokerala and the engine agree, a shared convention is the more
likely explanation than a shared bug.

Every response is cached under validation/.cache/vedintel, so a re-run costs
nothing. The free tier is 500 calls a month per key; VEDINTEL_API_KEY in .env
(and VEDINTEL_API_KEY_2, _3 ... if more are added) are used in turn.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import httpx

BASE_URL = "https://vedintelastroapi.com/api/v1"
CACHE = Path("validation/.cache/vedintel")


def _keys() -> list[str]:
    env: dict[str, str] = {}
    path = Path(".env")
    if path.exists():
        for line in path.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
    env.update({k: v for k, v in os.environ.items() if k.startswith("VEDINTEL_")})
    names = sorted((k for k in env if k.startswith("VEDINTEL_API_KEY")),
                   key=lambda k: (len(k), k))
    return [env[k] for k in names if env[k]]


def cache_path(endpoint: str, params: dict) -> Path:
    digest = hashlib.sha256(
        f"{endpoint}{json.dumps(params, sort_keys=True)}".encode()).hexdigest()[:20]
    return CACHE / f"{endpoint.replace('/', '--')}-{digest}.json"


class OutOfCalls(RuntimeError):
    pass


_active = 0
remaining: int | None = None


def fetch(endpoint: str, params: dict) -> dict:
    """One endpoint, cached. Raises OutOfCalls when every key is spent."""
    global _active, remaining
    path = cache_path(endpoint, params)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    keys = _keys()
    while _active < len(keys):
        response = httpx.get(f"{BASE_URL}/{endpoint}", params=params,
                             headers={"X-API-Key": keys[_active]}, timeout=60.0)
        header = response.headers.get("x-ratelimit-remaining")
        remaining = int(header) if header and header.isdigit() else remaining
        if response.status_code == 429 and remaining == 0:
            _active += 1
            continue
        if response.status_code == 429:
            time.sleep(2)
            continue
        try:
            payload = response.json()
        except ValueError:
            payload = {"status": response.status_code, "error": response.text[:300]}
        if response.status_code == 200:
            CACHE.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload), encoding="utf-8")
        return payload
    raise OutOfCalls("every VedIntel key is out of calls")
