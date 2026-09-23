"""Verify yoga detection against Prokerala's /astrology/yoga endpoint.

Costs 200 credits per chart. Responses are cached under validation/.cache/, so
re-runs are free; delete the cache to refetch.

    python validation/construct_yoga_charts.py     # free, picks the charts
    python validation/against_prokerala_yogas.py   # paid, verifies them
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, ".")
from astro_engine import yogas  # noqa: E402
from astro_engine.chart import BirthData  # noqa: E402
from engine_source import build_chart as build  # noqa: E402
from validation.against_prokerala import fetch  # noqa: E402

CHARTS = Path("validation/yoga_charts.json")
AYANAMSA_LAHIRI = 1


def prokerala_yogas(entry: dict) -> dict[str, bool]:
    payload = fetch("yoga", {
        "ayanamsa": AYANAMSA_LAHIRI,
        "coordinates": f"{entry['latitude']},{entry['longitude']}",
        "datetime": entry["datetime"],
    })
    out = {}
    for group in payload["data"]["yoga_details"]:
        for item in group.get("yoga_list", []):
            out[item["name"]] = item["has_yoga"]
    return out


def ours(entry: dict) -> dict[str, bool]:
    local = entry["local"]
    year, month, rest = local.split("-", 2)
    day, clock = rest.split("T")
    hour, minute, *_ = clock.split(":")
    chart = build(
        BirthData(int(year), int(month), int(day), int(hour), int(minute), 0,
                  entry["latitude"], entry["longitude"]),
        vargas=["D1"], dasha_depth=1,
    )
    return {y.name: y.present for y in yogas.detect(chart)}


def main() -> int:
    if not CHARTS.exists():
        print("run validation/construct_yoga_charts.py first")
        return 1
    plan = json.loads(CHARTS.read_text())
    entries = plan["charts"]
    print(f"Verifying {len(entries)} charts against /astrology/yoga "
          f"({len(entries) * 200} credits, cached after the first run)\n")

    agreements: dict[str, list[bool]] = defaultdict(list)
    disagreements: dict[str, list[dict]] = defaultdict(list)

    for index, entry in enumerate(entries, 1):
        try:
            theirs = prokerala_yogas(entry)
        except Exception as exc:
            print(f"{index}. {entry['local'][:10]} {entry['place']}: SKIPPED ({exc})")
            continue
        mine = ours(entry)

        wrong = [n for n in theirs if n in mine and mine[n] != theirs[n]]
        print(f"{index}. {entry['local'][:16]} {entry['place']:8} lagna {entry['lagna']:12} "
              f"{len(theirs) - len(wrong)}/{len(theirs)} agree")
        for name in sorted(theirs):
            if name not in mine:
                continue
            match = mine[name] == theirs[name]
            agreements[name].append(match)
            if not match:
                disagreements[name].append({
                    "chart": f"{entry['local'][:10]} {entry['place']}",
                    "engine": mine[name],
                    "prokerala": theirs[name],
                })
                print(f"     {name:22} engine={str(mine[name]):5} "
                      f"prokerala={str(theirs[name]):5}")

    print("\n" + "=" * 68)
    print(f"  {'yoga':24} {'charts':>7} {'agree':>7}  status")
    perfect = 0
    for name in sorted(agreements):
        results = agreements[name]
        hits = sum(results)
        ok = hits == len(results)
        perfect += ok
        print(f"  {name:24} {len(results):>7} {hits:>7}  {'ok' if ok else 'MISMATCH'}")

    print(f"\n{perfect}/{len(agreements)} yogas agree on every chart tested")
    if disagreements:
        print("\nDisagreements to investigate:")
        for name, cases in disagreements.items():
            print(f"  {name}:")
            for case in cases:
                print(f"    {case['chart']}: engine={case['engine']} "
                      f"prokerala={case['prokerala']}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
