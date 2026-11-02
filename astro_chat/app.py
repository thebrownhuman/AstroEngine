"""astro_chat FastAPI app: sessions grounded in one engine call, chat via an
OpenAI-compatible gateway. See docs/ASTRO-CHAT.md.

Run: uvicorn astro_chat.app:app --port 8001
"""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

from astro_engine import guard

from . import checks, facts
from .retrieval import BookIndex

log = logging.getLogger("astro_chat")

MAX_ATTEMPTS = 4
SNIPPET_CHARS = 300
MAX_HISTORY_TURNS = 20

SYSTEM_PROMPT = """You are a careful Vedic astrology (Jyotisha) assistant.
Answer only from the CHART FACTS and BOOK PASSAGES below. The chart facts were
computed by an audited engine and are authoritative: never change a sign,
house, dignity, dasha date or strength, and never invent placements that are
not listed. When you state a chart fact, cite it as [facts]. When you use a
book passage, cite its tag, e.g. [P2]. If the facts and passages do not
answer the question, say so plainly. Do not use outside astrology sources.

CHART FACTS ({name})
{facts}

BOOK PASSAGES
{passages}
"""


def _env(name: str, default: str = "") -> str:
    # Compose passes unset variables as empty strings; treat those as unset.
    return os.environ.get(name, "").strip() or default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    return default if not raw else raw in ("1", "true", "yes", "on")


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds")


class SessionRequest(BaseModel):
    date: str = Field(..., max_length=32)
    time: str = Field(..., max_length=32)
    place: str | None = Field(None, max_length=200)
    latitude: float | None = Field(None, ge=-90.0, le=90.0)
    longitude: float | None = Field(None, ge=-180.0, le=180.0)
    timezone: str | None = Field(None, max_length=64)
    name: str | None = Field(None, max_length=100)


class MessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


@dataclass
class Session:
    id: str
    name: str | None
    facts: str
    summary: str
    placements: dict
    expires: float
    history: list[dict] = field(default_factory=list)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class SessionStore:
    def __init__(self, ttl_seconds: float):
        self.ttl = ttl_seconds
        self.sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def _sweep(self, now: float):
        for sid in [s for s, v in self.sessions.items() if v.expires <= now]:
            del self.sessions[sid]

    def add(self, **kw) -> Session:
        now = time.time()
        with self._lock:
            self._sweep(now)
            s = Session(id=secrets.token_urlsafe(16), expires=now + self.ttl, **kw)
            self.sessions[s.id] = s
            return s

    def touch(self, sid: str) -> Session:
        now = time.time()
        with self._lock:
            self._sweep(now)
            s = self.sessions.get(sid)
            if s is None:
                raise HTTPException(404, "session not found or expired")
            s.expires = now + self.ttl
            return s

    def delete(self, sid: str) -> bool:
        with self._lock:
            return self.sessions.pop(sid, None) is not None


async def _engine_post(client: httpx.AsyncClient, path: str, body: dict) -> dict:
    try:
        r = await client.post(path, json=body)
    except httpx.HTTPError as exc:
        log.warning("engine %s failed: %s", path, type(exc).__name__)
        raise HTTPException(502, "astro engine unreachable") from exc
    if 400 <= r.status_code < 500 and r.status_code not in (401, 403, 429):
        try:
            detail = r.json().get("detail", r.text)
        except ValueError:
            detail = r.text
        raise HTTPException(r.status_code, detail)
    if r.status_code != 200:
        log.warning("engine %s returned %s", path, r.status_code)
        raise HTTPException(502, f"astro engine error ({r.status_code})")
    return r.json()


async def _llm_complete(client: httpx.AsyncClient, payload: dict) -> dict:
    base = float(_env("CHAT_RETRY_BASE", "1.0"))
    for attempt in range(MAX_ATTEMPTS):
        try:
            r = await client.post("/chat/completions", json=payload)
            status = r.status_code
        except httpx.TransportError as exc:
            status, r = 0, None
            log.warning("llm transport error: %s", type(exc).__name__)
        if status == 200:
            return r.json()["choices"][0]["message"]
        if status and status != 429 and status < 500:
            log.warning("llm returned %s", status)
            raise HTTPException(502, f"LLM gateway error ({status})")
        if attempt < MAX_ATTEMPTS - 1:
            await asyncio.sleep(base * 2 ** attempt)
    raise HTTPException(502, "LLM gateway unavailable after retries")


def create_app(engine_transport=None, llm_transport=None, books_dir: str | None = None) -> FastAPI:
    app = FastAPI(title="astro_chat", version="0.1.0",
                  description="Chart-grounded chat over the astro_engine.")
    app.add_middleware(guard.Guard)
    guard.configure()

    ttl = float(_env("CHAT_SESSION_TTL_MIN", "30")) * 60
    app.state.sessions = store = SessionStore(ttl)
    app.state.books = books = BookIndex.load(
        books_dir or _env("CHAT_BOOKS_DIR", "/app/books"))
    log.info("astro_chat: %d book chunks loaded", len(books.chunks))

    def engine_client() -> httpx.AsyncClient:
        key = _env("ASTRO_ENGINE_KEY")
        return httpx.AsyncClient(
            base_url=_env("ASTRO_ENGINE_URL", "http://astro-engine:8000"),
            headers={"X-API-Key": key} if key else {},
            transport=engine_transport, timeout=60)

    def llm_client() -> httpx.AsyncClient:
        key = _env("DEEPSEEK_API_KEY")
        return httpx.AsyncClient(
            base_url=_env("DEEPSEEK_BASE_URL", "http://100.72.157.104:9090/v1"),
            headers={"Authorization": f"Bearer {key}"} if key else {},
            transport=llm_transport, timeout=180)

    @app.get("/health")
    def health():
        return {"status": "ok", "sessions": len(store.sessions),
                "book_chunks": len(books.chunks)}

    @app.post("/v1/sessions")
    async def create_session(req: SessionRequest):
        birth = req.model_dump(exclude_none=True, exclude={"name"})
        async with engine_client() as client:
            chart, rules, shad = await asyncio.gather(
                _engine_post(client, "/v1/chart", {**birth, "include_yogas": True}),
                _engine_post(client, "/v1/rules", birth),
                _engine_post(client, "/v1/shadbala", birth))
        s = store.add(name=req.name, facts=facts.fact_sheet(chart, rules, shad),
                      summary=facts.summary(chart), placements=facts.placements(chart))
        return {"session_id": s.id, "expires_at": _iso(s.expires), "summary": s.summary}

    @app.get("/v1/sessions/{sid}")
    def get_session(sid: str):
        s = store.touch(sid)
        return {"session_id": s.id, "name": s.name, "summary": s.summary,
                "facts": s.facts, "history": s.history, "expires_at": _iso(s.expires)}

    @app.delete("/v1/sessions/{sid}", status_code=204)
    def delete_session(sid: str):
        if not store.delete(sid):
            raise HTTPException(404, "session not found or expired")
        return Response(status_code=204)

    @app.post("/v1/sessions/{sid}/messages")
    async def message(sid: str, req: MessageRequest):
        s = store.touch(sid)
        async with s.lock:
            hits = books.search(req.message, k=int(_env("CHAT_TOP_K", "5")))
            passages = "\n\n".join(
                f"[P{i}] {h.book}" + (f", ch.{h.chapter}" if h.chapter else "")
                + (f", p.{h.page}" if h.page else "") + f"\n{h.text}"
                for i, h in enumerate(hits, 1)) or "(none found)"
            system = SYSTEM_PROMPT.format(name=s.name or "native", facts=s.facts,
                                          passages=passages)
            history = s.history[-2 * MAX_HISTORY_TURNS:]
            payload = {
                "model": _env("DEEPSEEK_MODEL", "deepseek-chat"),
                "messages": [{"role": "system", "content": system}, *history,
                             {"role": "user", "content": req.message}],
                "thinking_mode": _env_bool("CHAT_THINKING", True),
                "search_enabled": _env_bool("CHAT_SEARCH", False),
            }
            async with llm_client() as client:
                msg = await _llm_complete(client, payload)
            reply = (msg.get("content") or "").strip()
            s.history += [{"role": "user", "content": req.message},
                          {"role": "assistant", "content": reply}]
        out = {
            "reply": reply,
            "sources": [{"ref": f"P{i}", "book": h.book, "chapter": h.chapter,
                         "page": h.page, "snippet": h.text[:SNIPPET_CHARS]}
                        for i, h in enumerate(hits, 1)],
            "checks": checks.check_reply(reply, s.placements),
            "expires_at": _iso(s.expires),
        }
        if _env_bool("CHAT_RETURN_REASONING", False):
            out["reasoning"] = msg.get("reasoning_content")
        return out

    return app


app = create_app()
