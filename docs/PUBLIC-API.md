# Public API at api.shivanshmishra.in

The engine is exposed through a Cloudflare Tunnel: no inbound port is opened on
the homelab, cloudflared dials out to Cloudflare and Cloudflare forwards
`https://api.shivanshmishra.in` to the engine on `localhost:8000`.

## What the engine enforces

Configured by environment variables on the `astro-engine` container
(`astro_engine/guard.py`). Only `/v1/*` is guarded; `/health`, `/docs` and
`/openapi.json` stay open.

| Variable | Meaning | Default |
|---|---|---|
| `ASTRO_API_KEYS` | Comma-separated keys accepted in the `X-API-Key` header. Empty disables auth and logs a warning. | empty (auth off) |
| `ASTRO_RATE_LIMIT` | Requests per minute per key (per client IP, from `CF-Connecting-IP`, when auth is off). `0` disables. | 60 with auth on, none with auth off |
| `ASTRO_CORS_ORIGINS` | Comma-separated browser origins allowed by CORS. | empty (no CORS) |

Missing or wrong key: `401 {"detail": "missing or invalid X-API-Key header"}`.
Over the limit: `429` with a `Retry-After` header in seconds.

**Never expose the tunnel without `ASTRO_API_KEYS` set.**

## One-time setup (manual)

The homelab already runs cloudflared as a systemd service with
`/etc/cloudflared/config.yml`; the API is one more ingress rule on that tunnel.

1. Generate one key per client, e.g. `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
2. In the homelab `.env` next to `docker-compose.yml` (gitignored):

   ```
   ASTRO_API_KEYS=<key1>,<key2>
   # optional
   ASTRO_RATE_LIMIT=60
   ASTRO_CORS_ORIGINS=https://shivanshmishra.in
   ```

   then `docker compose up -d astro-engine`.
3. Add the ingress rule in `/etc/cloudflared/config.yml`, above the final
   catch-all `- service: http_status:404`:

   ```yaml
   ingress:
     - hostname: api.shivanshmishra.in
       service: http://localhost:8000
   ```

   then `sudo systemctl restart cloudflared`.
4. DNS: a proxied CNAME `api` → `<tunnel-id>.cfargotunnel.com` in the
   shivanshmishra.in zone (or `cloudflared tunnel route dns <tunnel> api.shivanshmishra.in`).
5. Check: `curl https://api.shivanshmishra.in/health` returns `"status": "ok"`,
   and a `/v1/` call without a key returns 401.

Rotating a key: edit `ASTRO_API_KEYS`, then `docker compose up -d astro-engine`.

## Calling it

```bash
curl -s https://api.shivanshmishra.in/v1/chart/summary \
  -H "X-API-Key: $ASTRO_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"date": "1990-01-15", "time": "08:30", "place": "Delhi"}'
```

Validation scripts that hit a deployment send the key from `ASTRO_API_KEY`:

```bash
ASTRO_ENGINE_URL=https://api.shivanshmishra.in ASTRO_API_KEY=<key> python validation/live_api_audit.py
```

## Cloudflare WAF rate limit (recommended)

The in-process limiter only protects the engine after the request has reached
it. Add an edge rule so floods never cross the tunnel: **Security** → **WAF** →
**Rate limiting rules** → create:

- If incoming requests match: `(http.host eq "api.shivanshmishra.in" and starts_with(http.request.uri.path, "/v1/"))`
- Characteristics: IP (the free plan only offers IP)
- Rate: 100 requests per 1 minute (a little above the engine's per-key limit)
- Action: Block for 1 minute (free plan: 10 seconds)

Optionally add a custom WAF rule blocking everything except `/health`, `/docs`,
`/openapi.json` and `/v1/*` on that hostname.
