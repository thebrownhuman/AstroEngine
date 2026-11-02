"""Eval bench for the grounded /v1/ask layer (astro_llm).

Runs every case in ask_cases.yaml through astro_llm.ask in-process, against
the real model, and scores three things:

- factual accuracy: the answer contains the value the engine computes
  (expected values are read from the engine's own chart, never hand-typed);
- faithfulness: share of submitted claims whose evidence paths resolve;
- refusal correctness: predictions refused, interpretation answered fact-only.

Needs DEEPSEEK_API_KEY + DEEPSEEK_BASE_URL or ANTHROPIC_API_KEY; without them the bench prints a notice and exits 0.

    python validation/ask_bench.py [--only CASE_ID ...] [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

CASES = Path(__file__).with_name("ask_cases.yaml")

# Language that goes beyond what an engine field states.
INTERPRETIVE = re.compile(
    r"\b(you will|you'll|indicates?|suggests?|signif(?:y|ies)|promis\w+|"
    r"blessed|fortunate|unfortunate|auspicious for you|bring(?:s)? you|"
    r"your (?:spouse|partner) (?:will|is likely)|likely to)\b",
    re.IGNORECASE,
)
ABSENT = re.compile(r"\b(not|no|absent|does ?n[o']t|isn[o']t|without)\b", re.IGNORECASE)


def engine_chart(birth: dict) -> dict:
    from astro_llm.tools import call_engine
    return call_engine("get_vedic_chart", {
        "include_yogas": True, "include_transits": True,
        "vargas": ["D1", "D9", "D10"],
    }, birth)


def derived(chart: dict, name: str):
    if name.startswith("@next_md."):
        now = chart["current_dasha"]["chain"][0]
        periods = chart["dasha"]["mahadashas"]
        index = next(i for i, p in enumerate(periods) if p["start"] == now["start"])
        return periods[index + 1][name.split(".", 1)[1]]
    raise KeyError(name)


def expected_value(chart: dict, path: str):
    if path.startswith("@"):
        return derived(chart, path)
    from astro_llm.grounding import resolve
    return resolve({"c": chart}, f"c.{path}")


def present(value, answer: str) -> bool:
    text = str(value)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T.*", text):
        text = text[:10]
    return text.replace("_", " ").lower() in answer.replace("_", " ").lower()


def yoga_state(chart: dict, name: str) -> bool:
    for group in chart["yogas"]["yoga_details"]:
        for yoga in group["yoga_list"]:
            if yoga["name"] == name:
                return bool(yoga["has_yoga"])
    raise KeyError(name)


def score(case: dict, chart: dict, result: dict) -> dict:
    answer = result["answer"]
    kind = case["kind"]
    if kind == "fact":
        missing = [p for p in case["expect"] if not present(expected_value(chart, p), answer)]
        ok = not missing and not result["refused"]
        detail = f"missing {[(p, expected_value(chart, p)) for p in missing]}" if missing else ""
    elif kind == "yoga":
        has = yoga_state(chart, case["yoga"])
        says_absent = bool(ABSENT.search(answer))
        ok = (says_absent != has) and not result["refused"]
        detail = f"engine has_yoga={has}"
    elif kind == "refuse":
        ok = result["refused"]
        detail = "" if ok else "not refused"
    elif kind == "fact_only":
        hit = INTERPRETIVE.search(answer)
        ok = result["refused"] or not hit
        detail = f"interpretive: {hit.group(0)!r}" if hit else ""
    else:
        raise ValueError(kind)
    submitted = len(result["claims"]) + len(result["dropped_claims"])
    return {"id": case["id"], "kind": kind, "ok": ok, "detail": detail,
            "claims": len(result["claims"]), "dropped": len(result["dropped_claims"]),
            "submitted": submitted, "refused": result["refused"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    if not any(os.environ.get(k, "").strip() for k in ("DEEPSEEK_API_KEY", "ANTHROPIC_API_KEY")):
        print("SKIP: no LLM is configured (DEEPSEEK_API_KEY or ANTHROPIC_API_KEY); the ask bench needs the model.")
        return 0

    from astro_llm import ask, model_name

    spec = yaml.safe_load(CASES.read_text(encoding="utf-8"))
    reference = spec["reference_time"]
    charts = {name: {**birth, "reference_time": datetime.fromisoformat(reference)}
              for name, birth in spec["charts"].items()}
    computed = {name: engine_chart(birth) for name, birth in charts.items()}

    rows = []
    for case in spec["cases"]:
        if args.only and case["id"] not in args.only:
            continue
        try:
            result = ask(charts[case["chart"]], case["question"])
            row = score(case, computed[case["chart"]], result)
        except Exception as exc:  # report and carry on; one case must not sink the run
            row = {"id": case["id"], "kind": case["kind"], "ok": False,
                   "detail": f"error: {exc}", "claims": 0, "dropped": 0,
                   "submitted": 0, "refused": None}
        rows.append(row)
        print(f"{'PASS' if row['ok'] else 'FAIL'}  {row['id']:<22} "
              f"claims={row['claims']} dropped={row['dropped']} {row['detail']}")

    def rate(kinds):
        picked = [r for r in rows if r["kind"] in kinds]
        return (sum(r["ok"] for r in picked), len(picked))

    facts = rate({"fact", "yoga"})
    refusals = rate({"refuse", "fact_only"})
    submitted = sum(r["submitted"] for r in rows)
    kept = sum(r["claims"] for r in rows)
    print()
    print(f"model               : {model_name()}")
    print(f"factual accuracy    : {facts[0]}/{facts[1]}")
    print(f"refusal correctness : {refusals[0]}/{refusals[1]}")
    print(f"faithfulness        : {kept}/{submitted} claims resolved"
          + (f" ({kept / submitted:.1%})" if submitted else ""))
    if args.json:
        args.json.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return 0 if all(r["ok"] for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
