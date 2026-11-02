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
| POST | `/v1/sessions` | birth fields as `/v1/chart` (`date`, `time`, `place` or `latitude`/`longitude`, `timezone`) + optional `name` |
| GET | `/v1/sessions/{id}` | summary, fact sheet, history |
| DELETE | `/v1/sessions/{id}` | end session |
| POST | `/v1/sessions/{id}/messages` | `{message}` → `reply`, `sources`, `checks`, `expires_at` |

Session creation calls the engine once each for `/v1/chart`
(`include_yogas: true`), `/v1/rules` and `/v1/shadbala`. Engine 4xx errors are
passed through (bad date, unknown place); other failures give 502.

The fact sheet holds: lagna; each graha's sign, house, nakshatra-pada,
dignity, retrograde and combust state; house lords; the current dasha chain
with dates; present yogas (name + reason); shadbala `total_rupas`, `is_strong`
and rank; fired rules (id, meaning, source ch.v).

Sessions live in memory with a sliding TTL; a restart drops them. `sources`
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
