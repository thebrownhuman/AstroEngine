# `/v1/ask`: grounded questions about a chart

`POST /v1/ask` answers a question about one birth chart in plain language. A
Claude model reads the engine's output through the engine's own tools, and
every factual claim in the reply cites the exact field it came from. The
engine still does all the calculation; the model only reads.

The LLM layer lives in `astro_llm/`. `astro_engine/` does not import it except
inside this one handler.

## Calling it

Same birth fields as `/v1/chart` (`date`, `time`, `place` or
`latitude`/`longitude`, `timezone`, `ayanamsa`, `prokerala_compatible`,
`strict_bphs`, `reference_time`, ...), plus:

| field      | type                                   | notes                         |
|------------|----------------------------------------|-------------------------------|
| `question` | string, 1-2000 chars                   | required                      |
| `history`  | list of `{role: user|assistant, content}` | optional, up to 20 turns      |

```bash
curl -s https://api.shivanshmishra.in/v1/ask \
  -H "X-API-Key: $ASTRO_KEY" -H "Content-Type: application/json" \
  -d '{"date":"1990-01-15","time":"04:30","latitude":28.6139,"longitude":77.209,
       "timezone":"Asia/Kolkata","question":"Which mahadasha am I in and when does it end?"}'
```

Response:

```json
{
  "answer": "You are in Mars mahadasha, which ends on 2027-08-01.",
  "claims": [
    {"text": "Current mahadasha is Mars",
     "evidence": ["t1.current_dasha.chain.0.lord"],
     "provenance": ["bphs"], "flagged_provenance": []},
    {"text": "It ends 2027-08-01",
     "evidence": ["t1.current_dasha.chain.0.end"],
     "provenance": ["bphs"], "flagged_provenance": []}
  ],
  "dropped_claims": [],
  "tools_called": [{"result_id": "t1", "name": "get_vedic_chart", "input": {...}, "error": false}],
  "refused": false,
  "refusal_reason": null,
  "provenance_flags": [],
  "model": "claude-sonnet-5-5"
}
```

- **Evidence paths** are `<result_id>.<key>...`; `t1` is the first tool
  result, list items are numeric segments. Each path is checked against the
  tool results after the model answers. A claim with no evidence, or with any
  path that does not exist, moves to `dropped_claims` with the reason.
- **`provenance`** lists the `source` stamps found along each path.
  `flagged_provenance` / `provenance_flags` pick out `provider_compatible`
  and `unverified`: facts that follow Prokerala's convention or have no
  textual authority.
- **Birth data is fixed by the request.** The model chooses which blocks to
  include (yogas, transits, vargas), but cannot change whose chart it reads.

Auth and rate limit are the same `X-API-Key` guard as the rest of `/v1/`.

## Errors

| status | when |
|--------|------|
| 503    | the server has no `ANTHROPIC_API_KEY` |
| 422    | invalid birth data or question |
| 401/429| key missing/invalid, rate limited (guard) |

## What it answers

Facts the engine computes: lagna, planet signs, houses, nakshatra and pada,
dignity, combustion, divisional-chart signs, yogas present or absent (with the
engine's reason), dasha periods and dates, transits and Sade Sati phases,
panchanga, KP sub lords, matching scores, muhurta periods.

## What it will not answer

Interpretation and prediction rules are not loaded yet (Phase 2 of
`docs/PLAN-interpretation.md`). Asked what a placement *means* or what *will
happen*, it says so plainly, gives the relevant facts with evidence, and sets
`refused: true` for a pure prediction ("when will I marry", "will I be rich").
A narrow pattern check in code also sets `refused` on prediction phrasing if
the model did not. Asking it to ignore its rules gets the same answer. It
gives no medical, legal or financial advice.

## Configuration

| env                 | default             |
|---------------------|---------------------|
| `ANTHROPIC_API_KEY` | none (endpoint 503) |
| `ASTRO_LLM_MODEL`   | `claude-sonnet-5-5` |

## Evaluation

`validation/ask_bench.py` runs `validation/ask_cases.yaml` (37 cases on four
fixed charts) against the live model and reports factual accuracy (answer
matches the engine), faithfulness (claims whose evidence resolves) and refusal
correctness. Expected values come from the engine at run time, not from the
YAML. It skips cleanly without `ANTHROPIC_API_KEY`.
