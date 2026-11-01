"""Access control for public exposure: API keys, rate limiting and CORS.

All three are configured from the environment and are off by default, so a
private deployment (Tailscale, localhost) behaves exactly as before:

- ASTRO_API_KEYS      comma-separated keys accepted in the X-API-Key header.
                      Unset or empty disables auth (a warning is logged).
- ASTRO_RATE_LIMIT    requests per minute per key, or per client IP when auth is
                      off. Default 60 with auth on; with auth off there is no
                      limit unless this is set. 0 disables the limit.
- ASTRO_CORS_ORIGINS  comma-separated origins allowed by CORS. Unset: no CORS.

Only paths under /v1/ are guarded; /health, /docs and /openapi.json stay open.
The rate limiter is an in-process sliding window, which is right for the single
container this runs as. Behind Cloudflare, CF-Connecting-IP is the client IP.
"""

from __future__ import annotations

import hmac
import json
import logging
import math
import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field

from starlette.middleware.cors import CORSMiddleware

log = logging.getLogger("astro_engine")

GUARDED_PREFIX = "/v1/"
WINDOW_SECONDS = 60.0
DEFAULT_RATE_LIMIT = 60


def _split(value: str | None) -> tuple[str, ...]:
    return tuple(part.strip() for part in (value or "").split(",") if part.strip())


@dataclass
class Settings:
    api_keys: tuple[str, ...] = ()
    rate_limit: int = DEFAULT_RATE_LIMIT
    cors_origins: tuple[str, ...] = ()
    hits: dict[str, deque] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)

    @classmethod
    def from_env(cls) -> "Settings":
        raw_limit = os.environ.get("ASTRO_RATE_LIMIT", "").strip()
        settings = cls(
            api_keys=_split(os.environ.get("ASTRO_API_KEYS")),
            rate_limit=0,
            cors_origins=_split(os.environ.get("ASTRO_CORS_ORIGINS")),
        )
        if raw_limit:
            settings.rate_limit = int(raw_limit)
        elif settings.api_keys:
            settings.rate_limit = DEFAULT_RATE_LIMIT
        if not settings.api_keys:
            log.warning("ASTRO_API_KEYS is not set: /v1/* is open to anyone who can reach it")
        return settings

    def key_valid(self, presented: str) -> bool:
        presented_b = presented.encode()
        # Check every key so the time taken does not reveal which one matched.
        matched = False
        for key in self.api_keys:
            matched |= hmac.compare_digest(presented_b, key.encode())
        return matched

    def retry_after(self, bucket: str) -> int:
        """Record a hit for bucket; return 0 if allowed, else seconds to wait."""
        if self.rate_limit <= 0:
            return 0
        now = time.monotonic()
        with self.lock:
            hits = self.hits.setdefault(bucket, deque())
            while hits and now - hits[0] >= WINDOW_SECONDS:
                hits.popleft()
            if len(hits) >= self.rate_limit:
                return max(1, math.ceil(WINDOW_SECONDS - (now - hits[0])))
            hits.append(now)
            return 0


class Guard:
    """ASGI middleware applying the current Settings to every request."""

    settings: Settings = Settings()

    def __init__(self, app):
        self.app = app
        self._cors_for: tuple[str, ...] | None = None
        self._cors_app = app

    def _downstream(self):
        origins = self.settings.cors_origins
        if origins != self._cors_for:
            self._cors_for = origins
            self._cors_app = (
                CORSMiddleware(self.app, allow_origins=list(origins),
                               allow_methods=["GET", "POST"], allow_headers=["*"])
                if origins else self.app
            )
        return self._cors_app

    async def __call__(self, scope, receive, send):
        downstream = self._downstream()
        if (scope["type"] != "http" or not scope["path"].startswith(GUARDED_PREFIX)
                or scope["method"] == "OPTIONS"):
            return await downstream(scope, receive, send)

        settings = self.settings
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        key = headers.get("x-api-key", "")
        if settings.api_keys:
            if not key or not settings.key_valid(key):
                return await _reject(send, 401, "missing or invalid X-API-Key header", downstream, scope)
            bucket = "key:" + key
        else:
            client = scope.get("client")
            bucket = "ip:" + (headers.get("cf-connecting-ip")
                              or (client[0] if client else "unknown"))

        wait = settings.retry_after(bucket)
        if wait:
            return await _reject(send, 429, "rate limit exceeded", downstream, scope,
                                 [(b"retry-after", str(wait).encode())])
        await downstream(scope, receive, send)


async def _reject(send, status, detail, downstream, scope, extra=()):
    body = json.dumps({"detail": detail}).encode()
    headers = [(b"content-type", b"application/json"),
               (b"content-length", str(len(body)).encode()), *extra]
    if isinstance(downstream, CORSMiddleware):
        # Let browsers read the error from an allowed origin.
        origin = dict(scope["headers"]).get(b"origin")
        if origin and downstream.is_allowed_origin(origin.decode("latin-1")):
            headers.append((b"access-control-allow-origin", origin))
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


def configure() -> Settings:
    """(Re)read the environment and reset rate-limit state."""
    Guard.settings = Settings.from_env()
    return Guard.settings
