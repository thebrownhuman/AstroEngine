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
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Protocol
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field, model_validator

from astro_engine import guard

from . import checks, facts
from .retrieval import BookIndex

log = logging.getLogger("astro_chat")

MAX_ATTEMPTS = 4
SNIPPET_CHARS = 300
MAX_HISTORY_TURNS = 20
MAX_FACTS_CHARS = 20_000
SWEEP_SECONDS = 60

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


class BirthRequest(BaseModel):
    date: str = Field(..., max_length=32)
    time: str = Field(..., max_length=32)
    place: str | None = Field(None, max_length=200)
    latitude: float | None = Field(None, ge=-90.0, le=90.0)
    longitude: float | None = Field(None, ge=-180.0, le=180.0)
    timezone: str | None = Field(None, max_length=64)


class SessionRequest(BaseModel):
    """Birth data (the engine is called), or a chart computed earlier: either
    the fact sheet itself or the raw engine outputs to build it from."""

    date: str | None = Field(None, max_length=32)
    time: str | None = Field(None, max_length=32)
    place: str | None = Field(None, max_length=200)
    latitude: float | None = Field(None, ge=-90.0, le=90.0)
    longitude: float | None = Field(None, ge=-180.0, le=180.0)
    timezone: str | None = Field(None, max_length=64)
    name: str | None = Field(None, max_length=100)
    chart_id: str | None = Field(None, max_length=128)
    facts: str | None = Field(None, max_length=MAX_FACTS_CHARS)
    chart: dict | None = None
    rules: dict | None = None
    shadbala: dict | None = None

    @model_validator(mode="after")
    def _one_source(self):
        if not (self.facts or self.chart or (self.date and self.time)):
            raise ValueError("give date and time, a precomputed facts sheet, or chart")
        return self

    def birth(self) -> dict:
        return self.model_dump(include=set(BirthRequest.model_fields), exclude_none=True)


class MessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


@dataclass
class Session:
    id: str
    chart_id: str | None
    name: str | None
    facts: str
    summary: str
    placements: dict
    expires: float
    history: list[dict] = field(default_factory=list)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class SessionStore(Protocol):
    """What the app needs from session storage. In memory today; a Redis
    implementation would keep the same methods and TTL semantics."""

    def add(self, **fields) -> Session: ...
    def touch(self, sid: str) -> Session | None: ...  # get and slide the TTL
    def delete(self, sid: str) -> bool: ...
    def sweep(self) -> int: ...  # purge expired, return how many
    def __len__(self) -> int: ...


class InMemorySessionStore:
    def __init__(self, ttl_seconds: float):
        self.ttl = ttl_seconds
        self.sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def _purge(self, now: float) -> int:
        dead = [sid for sid, v in self.sessions.items() if v.expires <= now]
        for sid in dead:
            del self.sessions[sid]
        return len(dead)

    def sweep(self) -> int:
        with self._lock:
            return self._purge(time.time())

    def add(self, **fields) -> Session:
        now = time.time()
        with self._lock:
            self._purge(now)
            s = Session(id=secrets.token_urlsafe(16), expires=now + self.ttl, **fields)
            self.sessions[s.id] = s
            return s

    def touch(self, sid: str) -> Session | None:
        now = time.time()
        with self._lock:
            s = self.sessions.get(sid)
            if s is None or s.expires <= now:
                self.sessions.pop(sid, None)
                return None
            s.expires = now + self.ttl
            return s

    def delete(self, sid: str) -> bool:
        with self._lock:
            return self.sessions.pop(sid, None) is not None

    def __len__(self) -> int:
        return len(self.sessions)


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


def create_app(engine_transport=None, llm_transport=None, books_dir: str | None = None,
               store: SessionStore | None = None) -> FastAPI:
    ttl = float(_env("CHAT_SESSION_TTL_MIN", "30")) * 60
    store = store or InMemorySessionStore(ttl)

    @asynccontextmanager
    async def lifespan(app):
        async def sweeper():
            while True:
                await asyncio.sleep(SWEEP_SECONDS)
                if n := store.sweep():
                    log.info("astro_chat: purged %d expired sessions", n)
        task = asyncio.create_task(sweeper())
        yield
        task.cancel()

    app = FastAPI(title="astro_chat", version="0.2.0", lifespan=lifespan,
                  description="Chart-grounded chat over the astro_engine.")
    app.add_middleware(guard.Guard)
    guard.configure()

    app.state.sessions = store
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

    async def compute(birth: dict) -> tuple[dict, dict, dict]:
        async with engine_client() as client:
            return await asyncio.gather(
                _engine_post(client, "/v1/chart", {**birth, "include_yogas": True}),
                _engine_post(client, "/v1/rules", birth),
                _engine_post(client, "/v1/shadbala", birth))

    def live(sid: str) -> Session:
        s = store.touch(sid)
        if s is None:
            raise HTTPException(404, "session not found or expired")
        return s

    @app.get("/health")
    def health():
        return {"status": "ok", "sessions": len(store), "book_chunks": len(books.chunks)}

    @app.post("/v1/facts")
    async def compute_facts(req: BirthRequest):
        """Compute once; the caller stores the result and later opens sessions
        from it without the engine being called again."""
        chart, rules, shad = await compute(req.model_dump(exclude_none=True))
        return {"facts": facts.fact_sheet(chart, rules, shad), "summary": facts.summary(chart),
                "chart": chart, "rules": rules, "shadbala": shad}

    @app.post("/v1/sessions")
    async def create_session(req: SessionRequest):
        if req.facts:
            sheet = req.facts
            placements = facts.parse_placements(sheet)
            summary = sheet.splitlines()[0][:200]
        else:
            if req.chart:
                chart, rules, shad = req.chart, req.rules or {}, req.shadbala or {}
            else:
                chart, rules, shad = await compute(req.birth())
            try:
                sheet = facts.fact_sheet(chart, rules, shad)
                placements, summary = facts.placements(chart), facts.summary(chart)
            except (KeyError, TypeError) as exc:
                raise HTTPException(422, f"chart payload is not engine output: missing {exc}") from exc
        s = store.add(chart_id=req.chart_id, name=req.name, facts=sheet,
                      summary=summary, placements=placements)
        return {"session_id": s.id, "chart_id": s.chart_id, "expires_at": _iso(s.expires),
                "summary": s.summary}

    @app.get("/v1/sessions/{sid}")
    def get_session(sid: str):
        s = live(sid)
        return {"session_id": s.id, "chart_id": s.chart_id, "name": s.name,
                "summary": s.summary, "facts": s.facts, "history": s.history,
                "expires_at": _iso(s.expires)}

    @app.post("/v1/sessions/{sid}/heartbeat")
    def heartbeat(sid: str):
        s = live(sid)
        return {"session_id": s.id, "chart_id": s.chart_id, "expires_at": _iso(s.expires)}

    @app.delete("/v1/sessions/{sid}", status_code=204)
    def delete_session(sid: str):
        if not store.delete(sid):
            raise HTTPException(404, "session not found or expired")
        return Response(status_code=204)

    @app.post("/v1/sessions/{sid}/messages")
    async def message(sid: str, req: MessageRequest):
        s = live(sid)
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
            "chart_id": s.chart_id,
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
