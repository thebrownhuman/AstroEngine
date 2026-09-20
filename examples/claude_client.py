"""Claude reads a chart it is not allowed to compute.

The rule this file exists to enforce: the model never produces a number. It
calls the engine, receives exact positions, and only then writes prose. Accuracy
is a property of the engine, not of the model.

    pip install anthropic
    set ANTHROPIC_API_KEY=...
    python examples/claude_client.py "Born 15 January 1990, 04:30, Sultanpur UP"

Run it against the plumbing without spending tokens or needing a key:

    python examples/claude_client.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import httpx

ENGINE_URL = os.environ.get("ASTRO_ENGINE_URL", "http://127.0.0.1:8000")
MODEL = os.environ.get("ASTRO_MODEL", "claude-sonnet-5")
MAX_TURNS = 6

# Which endpoint each tool in /v1/tool-definitions is served by.
TOOL_ROUTES = {
    "get_vedic_chart": "/v1/chart",
    "get_kundli_matching": "/v1/matching",
    "get_muhurta": "/v1/muhurta",
    "get_kp_chart": "/v1/kp",
}

SYSTEM_PROMPT = """You are a Jyotisha (Vedic astrology) interpreter working from \
exact computed chart data.

## Hard rules

- You never calculate. Not positions, not house placements, not dasha dates, not
  ages, not transit timing. Every number and date you state must appear in the
  tool output. If it is not there, call the tool again with different arguments
  or say you do not have it.
- Call `get_vedic_chart` before saying anything about a chart. If the question
  involves timing, current periods, Sade Sati, or "what is happening now", set
  `include_transits` to true.
- Pass the birth place as `place` and let the engine resolve it. Do not invent
  coordinates. If the engine resolves a place you did not expect, say which
  place it used.

## Reading the data

- `grahas` gives each planet's sign, house, nakshatra, pada, dignity and
  retrogradation. `houses` gives the whole-sign layout from the Lagna.
- `panchanga.vara` is sunrise-based and is the correct one for interpretation.
  `panchanga.civil_vara` is the calendar weekday; do not use it for a reading.
- `current_dasha.chain` is the running mahadasha and antardasha.
- `transits.sade_sati` has exact phase dates. `transits.prokerala_style` mirrors
  a popular convention that labels the 4th and 8th houses as Sade Sati too;
  `strict_sade_sati` is the real 12th-1st-2nd definition. Prefer the strict one
  and mention the other only if relevant.
- Sade Sati is commonly said to last 7.5 years. The engine reports the real
  duration, which varies by which signs are involved. Quote the engine.

## Voice

- Ground every claim in a specific placement: "Saturn in the 2nd from Scorpio
  lagna, combust" rather than "Saturn is challenging".
- Be concrete and useful. No vague flattery, no hedging every sentence.
- Say plainly when the chart does not support a conclusion.
- Never give medical, legal or financial instructions. Astrological reasoning is
  not a substitute for professional advice, and you should say so if the user
  asks about health, money or legal decisions."""

DEFAULT_QUESTION = (
    "Born 15 January 1990 at 04:30 in Delhi, India. What does my chart say about "
    "career, and what period am I running right now?"
)


def engine_get(path: str, **params) -> dict:
    response = httpx.get(f"{ENGINE_URL}{path}", params=params, timeout=30.0)
    response.raise_for_status()
    return response.json()


def engine_post(path: str, payload: dict) -> dict:
    response = httpx.post(f"{ENGINE_URL}{path}", json=payload, timeout=60.0)
    if response.status_code == 422:
        # Hand validation errors back to the model so it can correct itself.
        return {"error": response.json().get("detail", "invalid request")}
    response.raise_for_status()
    return response.json()


def check_engine() -> dict:
    try:
        return engine_get("/health")
    except Exception as exc:
        raise SystemExit(
            f"cannot reach the engine at {ENGINE_URL}: {exc}\n"
            "Start it with:  .\\deploy\\serve.ps1"
        ) from exc


def dry_run() -> int:
    """Exercise the whole loop except the model call."""
    health = check_engine()
    print(f"engine     : {ENGINE_URL}")
    print(f"ephemeris  : {health['ephemeris']}")

    tools = engine_get("/v1/tool-definitions")
    assert {t["name"] for t in tools} == set(TOOL_ROUTES), \
        "a tool has no route; TOOL_ROUTES is out of date"
    print(f"tools      : {', '.join(t['name'] for t in tools)}")

    arguments = {
        "date": "1990-01-15",
        "time": "04:30",
        "place": "Delhi",
        "include_transits": True,
    }
    print(f"simulating tool_use with {json.dumps(arguments)}")
    chart = engine_post("/v1/chart", arguments)
    if "error" in chart:
        print(f"FAILED: {chart['error']}")
        return 1

    payload = json.dumps(chart)
    print(f"tool_result: {len(payload):,} bytes")
    print()
    print(f"  resolved place : {chart['input']['place']['label']}")
    print(f"  timezone       : {chart['input']['timezone']} "
          f"(UTC{chart['input']['utc_offset_hours']:+g})")
    print(f"  lagna          : {chart['lagna']['sign_en']} {chart['lagna']['dms']}")
    print(f"  vara           : {chart['panchanga']['vara']['name']} (sunrise) / "
          f"{chart['panchanga']['civil_vara']['name']} (civil)")
    chain = " > ".join(c["lord"] for c in chart["current_dasha"]["chain"])
    print(f"  current dasha  : {chain}")
    phase = chart["transits"]["prokerala_style"]["transit_phase"]
    print(f"  saturn phase   : {phase or 'none'}")
    print()
    periods = engine_post("/v1/muhurta", {"date": "1990-01-15", "place": "Delhi"})
    rahu = next(m for m in periods["inauspicious"] if m["name"] == "Rahu")
    print(f"  rahu kaal      : {rahu['period'][0]['start'][11:19]} to "
          f"{rahu['period'][0]['end'][11:19]}")

    print()
    print("Loop is wired correctly. Add ANTHROPIC_API_KEY to run it for real.")
    return 0


def converse(question: str) -> int:
    from anthropic import Anthropic

    check_engine()
    tools = engine_get("/v1/tool-definitions")
    client = Anthropic()

    messages: list[dict] = [{"role": "user", "content": question}]

    for _ in range(MAX_TURNS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            tools=tools,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            for block in response.content:
                if block.type == "text":
                    print(block.text)
            return 0

        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            route = TOOL_ROUTES.get(block.name)
            print(f"[engine] {block.name} {json.dumps(block.input)}", file=sys.stderr)
            if route is None:
                content = json.dumps({"error": f"unknown tool {block.name}"})
            else:
                content = json.dumps(engine_post(route, block.input))
            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": content,
            })
        messages.append({"role": "user", "content": results})

    print(f"gave up after {MAX_TURNS} turns", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", nargs="*", default=None)
    parser.add_argument("--dry-run", action="store_true",
                        help="exercise the plumbing without calling the model")
    args = parser.parse_args()

    if args.dry_run:
        return dry_run()
    return converse(" ".join(args.question) if args.question else DEFAULT_QUESTION)


if __name__ == "__main__":
    raise SystemExit(main())
