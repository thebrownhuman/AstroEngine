"""astro_chat: sessions, fact sheet, BM25 retrieval, LLM call and checks.

The engine runs in-process over ASGI, the LLM is an httpx MockTransport and the
books are small fixture files, so nothing here needs the network.
"""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from astro_chat import app as chat_app
from astro_chat import checks, facts, retrieval
from astro_engine import guard
from astro_engine.api import app as engine_app

BIRTH = {"date": "1990-01-15", "time": "04:30", "latitude": 28.61,
         "longitude": 77.21, "timezone": "Asia/Kolkata"}

BOOK = """CHAPTER 24 Effects of the Lords of Houses
Page 12
If the lord of the ascendant is in the ascendant itself, the native will be
healthy, valorous, intelligent and fickle minded, with two wives.
\f
Page 13
If the lord of the second is in the eighth, the native will have abundant
land and wealth but little marital happiness.
CHAPTER 27 Shadbala
Page 40
Uchcha bala is found by taking the distance of the planet from its point of
debilitation and dividing it by three.
"""
GARBAGE = "~~ |||| 1. ;; 2'3 ,, .. %% ## 77 88 99 // \\\\ -- __ ++ == ** " * 40


@pytest.fixture
def books(tmp_path):
    (tmp_path / "bphs_santhanam_v1.txt").write_text(BOOK, encoding="utf-8")
    (tmp_path / "vol1.txt").write_text(GARBAGE, encoding="utf-8")
    return tmp_path


class FakeLLM:
    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []

    def __call__(self, request):
        self.requests.append(json.loads(request.content))
        status, body = self.replies.pop(0)
        return httpx.Response(status, json=body)


def completion(text, reasoning="thinking..."):
    return 200, {"choices": [{"message": {"role": "assistant", "content": text,
                                          "reasoning_content": reasoning}}]}


@pytest.fixture
def client_for(books, monkeypatch):
    monkeypatch.delenv("ASTRO_API_KEYS", raising=False)
    monkeypatch.setenv("CHAT_RETRY_BASE", "0")
    made = []

    def make(llm):
        app = chat_app.create_app(
            engine_transport=httpx.ASGITransport(app=engine_app),
            llm_transport=httpx.MockTransport(llm),
            books_dir=str(books),
        )
        c = TestClient(app)
        made.append(c)
        return c

    yield make
    monkeypatch.undo()  # restore env before re-reading it
    guard.configure()


def new_session(client):
    r = client.post("/v1/sessions", json={**BIRTH, "name": "Test"})
    assert r.status_code == 200, r.text
    return r.json()


# ---- retrieval -------------------------------------------------------------

def test_bm25_ranks_relevant_chunk_and_tags_it(books):
    index = retrieval.BookIndex.load(str(books))
    hits = index.search("lord of the second in the eighth wealth", k=2)
    assert hits
    top = hits[0]
    assert "eighth" in top.text
    assert top.book == "bphs_santhanam_v1"
    assert top.page == 13
    assert top.chapter == "24"


def test_garbage_chunks_are_dropped(books):
    index = retrieval.BookIndex.load(str(books))
    assert all(c.book != "vol1" for c in index.chunks)


def test_alpha_ratio():
    assert retrieval.alpha_ratio("abc def") > 0.8
    assert retrieval.alpha_ratio(GARBAGE) < 0.3


def test_missing_books_dir_gives_empty_index(tmp_path):
    index = retrieval.BookIndex.load(str(tmp_path / "nope"))
    assert index.search("anything") == []


# ---- fact sheet ------------------------------------------------------------

@pytest.fixture(scope="module")
def engine_data():
    c = TestClient(engine_app)
    return (c.post("/v1/chart", json={**BIRTH, "include_yogas": True}).json(),
            c.post("/v1/rules", json=BIRTH).json(),
            c.post("/v1/shadbala", json=BIRTH).json())


def test_fact_sheet_contents_and_size(engine_data):
    sheet = facts.fact_sheet(*engine_data)
    assert "Lagna: Vrischika" in sheet
    assert "Sun: Makara (Capricorn), house 3" in sheet
    assert "Uttara Ashadha pada 2" in sheet
    assert "House 1 (Vrischika): lord Mars" in sheet
    assert "mahadasha Mars" in sheet
    assert "bphs.house_lords.1_in_1" in sheet and "ch.26 v.1" in sheet
    assert "rupas" in sheet
    assert "Gajakesari" not in sheet  # absent yogas are left out
    assert 2000 < len(sheet) < 9000


def test_placements_map(engine_data):
    p = facts.placements(engine_data[0])
    assert p["Sun"] == {"sign": "Makara", "sign_en": "Capricorn", "house": 3}


# ---- consistency check -----------------------------------------------------

def test_checks_flag_wrong_sign_and_house(engine_data):
    p = facts.placements(engine_data[0])
    reply = ("The Sun in Capricorn gives discipline. Mars is in Leo, and "
             "the Sun in the 5th house shows creativity. Mars in the 1st house.")
    found = checks.check_reply(reply, p)
    bad = [c for c in found if not c["ok"]]
    assert {(c["graha"], c["kind"]) for c in bad} == {("Mars", "sign"), ("Sun", "house")}
    assert any(c["ok"] and c["graha"] == "Sun" and c["kind"] == "sign" for c in found)


# ---- API -------------------------------------------------------------------

def test_session_lifecycle(client_for):
    c = client_for(FakeLLM([]))
    s = new_session(c)
    assert s["session_id"] and s["expires_at"]
    assert "Vrischika" in s["summary"]
    got = c.get(f"/v1/sessions/{s['session_id']}").json()
    assert got["name"] == "Test" and "Lagna" in got["facts"]
    assert c.delete(f"/v1/sessions/{s['session_id']}").status_code == 204
    assert c.get(f"/v1/sessions/{s['session_id']}").status_code == 404


def test_engine_error_passes_through(client_for):
    c = client_for(FakeLLM([]))
    r = c.post("/v1/sessions", json={**BIRTH, "date": "1990-13-45"})
    assert r.status_code == 422


def test_message_builds_prompt_and_returns_checked_reply(client_for):
    llm = FakeLLM([completion("Mars is in Leo [facts]."),
                   completion("Second answer.")])
    c = client_for(llm)
    sid = new_session(c)["session_id"]
    r = c.post(f"/v1/sessions/{sid}/messages",
               json={"message": "What does the lord of the ascendant in the ascendant give?"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["reply"] == "Mars is in Leo [facts]."
    assert "reasoning" not in body and "reasoning_content" not in json.dumps(body)
    assert body["sources"] and all(len(s["snippet"]) <= 300 for s in body["sources"])
    assert any(not ch["ok"] and ch["graha"] == "Mars" for ch in body["checks"])

    req = llm.requests[0]
    assert req["thinking_mode"] is True and req["search_enabled"] is False
    system = req["messages"][0]
    assert system["role"] == "system"
    assert "Lagna: Vrischika" in system["content"] and "ascendant" in system["content"]
    assert req["messages"][-1] == {"role": "user", "content":
                                   "What does the lord of the ascendant in the ascendant give?"}

    c.post(f"/v1/sessions/{sid}/messages", json={"message": "And then?"})
    roles = [m["role"] for m in llm.requests[1]["messages"]]
    assert roles == ["system", "user", "assistant", "user"]


def test_env_flags(client_for, monkeypatch):
    monkeypatch.setenv("CHAT_THINKING", "false")
    monkeypatch.setenv("CHAT_SEARCH", "true")
    llm = FakeLLM([completion("ok")])
    c = client_for(llm)
    sid = new_session(c)["session_id"]
    c.post(f"/v1/sessions/{sid}/messages", json={"message": "hi"})
    assert llm.requests[0]["thinking_mode"] is False
    assert llm.requests[0]["search_enabled"] is True


def test_retries_429_and_5xx(client_for):
    llm = FakeLLM([(429, {"error": "slow"}), (502, {"error": "bad"}), completion("done")])
    c = client_for(llm)
    sid = new_session(c)["session_id"]
    r = c.post(f"/v1/sessions/{sid}/messages", json={"message": "hi"})
    assert r.status_code == 200 and r.json()["reply"] == "done"
    assert len(llm.requests) == 3


def test_gives_up_after_retries(client_for):
    llm = FakeLLM([(429, {})] * 4)
    c = client_for(llm)
    sid = new_session(c)["session_id"]
    r = c.post(f"/v1/sessions/{sid}/messages", json={"message": "hi"})
    assert r.status_code == 502
    # A failed turn is not recorded in history.
    assert c.get(f"/v1/sessions/{sid}").json()["history"] == []


def test_unknown_session_404(client_for):
    c = client_for(FakeLLM([]))
    assert c.post("/v1/sessions/nope/messages", json={"message": "x"}).status_code == 404


def test_session_expires(client_for, monkeypatch):
    c = client_for(FakeLLM([]))
    sid = new_session(c)["session_id"]
    store = c.app.state.sessions
    store.sessions[sid].expires -= 10_000
    assert c.get(f"/v1/sessions/{sid}").status_code == 404


def test_health_and_guard(client_for, monkeypatch):
    c = client_for(FakeLLM([]))
    h = c.get("/health").json()
    assert h["status"] == "ok" and h["book_chunks"] >= 2
    monkeypatch.setenv("ASTRO_API_KEYS", "k1")
    guard.configure()
    assert c.post("/v1/sessions", json=BIRTH).status_code == 401
    assert c.get("/health").status_code == 200
