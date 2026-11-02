# astro_chat: chart-grounded chat service

`astro_chat` is a separate FastAPI app (port 8001, same Docker image as the
engine). The engine stays a pure, audited calculator; everything LLM-shaped
lives here. It replaces the tool-call loop of `/v1/ask`, which failed because
large tool results reached the model truncated.

## Design

- **Facts go into the prompt.** No tool calls. A session computes the chart
  once and keeps a compact fact sheet (about 5-8k characters).
- **Books by retrieval.** Pure-Python BM25 over chunked `.txt` books. Chunks
  that are mostly non-alphabetic (OCR garbage) are dropped.
- **Light verification.** Graha-sign and graha-house claims in the reply are
  checked against the fact sheet; mismatches are reported in `checks`.

## Endpoints

All `/v1/*` paths use the engine's `Guard` (`ASTRO_API_KEYS`, `ASTRO_RATE_LIMIT`,
`ASTRO_CORS_ORIGINS`).

| Method | Path | |
|---|---|---|
| GET | `/health` | liveness, book chunk count |
| POST | `/v1/facts` | birth fields → `facts`, `summary` and raw `chart`, `rules`, `shadbala` (for the app to store) |
| POST | `/v1/sessions` | see "Opening a session" |
| GET | `/v1/sessions/{id}` | summary, fact sheet, history, `chart_id` |
| POST | `/v1/sessions/{id}/heartbeat` | slide the TTL; returns `expires_at` |
| DELETE | `/v1/sessions/{id}` | end session |
| POST | `/v1/sessions/{id}/messages` | `{message}` → `reply`, `sources`, `checks`, `expires_at` |

## Opening a session

`POST /v1/sessions` takes optional `chart_id` and `name` plus one of:

1. `facts`: a fact sheet stored earlier (from `/v1/facts`). No engine call.
2. `chart` (+ `rules`, `shadbala`): raw engine outputs stored earlier; the
   sheet is built from them (`astro_chat.facts.fact_sheet`, a pure function).
   No engine call.
3. Birth fields as `/v1/chart` (`date`, `time`, `place` or
   `latitude`/`longitude`, `timezone`): the engine is called.

`chart_id` is echoed in every session and message response. A stored sheet
carries the dasha chain "as of" the day it was computed, so the storing app
should refresh it when the current period ends.

With birth fields, session creation calls the engine once each for `/v1/chart`
(`include_yogas: true`), `/v1/rules` and `/v1/shadbala`. Engine 4xx errors are
passed through (bad date, unknown place); other failures give 502.

The fact sheet holds: lagna; each graha's sign, house, nakshatra-pada,
dignity, retrograde and combust state; house lords; the current dasha chain
with dates; present yogas (name + reason); shadbala `total_rupas`, `is_strong`
and rank; fired rules (id, meaning, source ch.v).

## Session lifetime

A session lives while the user is active on that chart: it expires
`CHAT_SESSION_TTL_MIN` (30) minutes after the last activity. Every message,
`GET` and `heartbeat` slides it; the frontend calls `heartbeat` while the chart
is open. Expired sessions are purged lazily on access and by a sweep every
60 s, and the fact sheet and history go with them. A restart drops all
sessions.

Persistence is the calling app's job (saved charts, conversation logs);
astro_chat has no database. Storage sits behind the `SessionStore` protocol in
`astro_chat/app.py` (`add`, `touch`, `delete`, `sweep`), implemented by
`InMemorySessionStore`; a Redis store can be passed to `create_app(store=...)`.

 `sources`
are snippets of at most 300 characters, never whole pages. `reasoning_content`
is not returned unless `CHAT_RETURN_REASONING=true`.

## Environment

| Variable | Default | |
|---|---|---|
| `ASTRO_ENGINE_URL` | `http://astro-engine:8000` | engine base URL |
| `ASTRO_ENGINE_KEY` | empty | sent as `X-API-Key` to the engine |
| `DEEPSEEK_BASE_URL` | `http://100.72.157.104:9090/v1` | OpenAI-compatible gateway |
| `DEEPSEEK_API_KEY` | empty | bearer token |
| `DEEPSEEK_MODEL` | `deepseek-chat` | |
| `CHAT_THINKING` | `true` | sends `thinking_mode` |
| `CHAT_SEARCH` | `false` | sends `search_enabled`; off so web astrology stays out |
| `CHAT_SESSION_TTL_MIN` | `30` | sliding TTL |
| `CHAT_BOOKS_DIR` | `/app/books` | `.txt` books (not in git) |
| `CHAT_TOP_K` | `5` | passages per message |
| `CHAT_RETURN_REASONING` | `false` | include `reasoning` in replies |

LLM calls retry 429 and 5xx with exponential backoff (4 attempts).

## Books

Put the usable OCR text in `./books` next to `docker-compose.yml` (mounted
read-only): `bphs_santhanam_v1.txt`, `bphs_santhanam_v2.txt`,
`graha_bhava_balas.txt`. The Sharma `vol1/vol2.txt` may be added; the quality
filter drops their garbage chunks. Image-only PDFs are not used.

Passages are tagged with book, page (form feeds or `Page N` markers) and
chapter (`CHAPTER N` / `Ch. N` headings) when detectable.
