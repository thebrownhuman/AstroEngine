"""Pick charts that tell competing yoga rules apart.

Fitting rules to 15 charts produced 14 different formulas that all fit Daridra
perfectly - a sign of too little signal, not of success. So instead of guessing,
choose new charts where the surviving candidates disagree most, and let the API
adjudicate. Each such chart splits the candidate set roughly in half.

    python validation/discriminate_yogas.py          # free, proposes charts
    python validation/discriminate_yogas.py --verify # paid, 200 credits each
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, ".")
from astro_engine import yogas  # noqa: E402
from astro_engine.chart import BirthData, build  # noqa: E402
from validation.against_prokerala import fetch  # noqa: E402

OUTPUT = Path("validation/yoga_discriminators.json")
CHARTS_PER_ROUND = 6

PLACES = [
    ("Delhi", 28.6139, 77.2090),
    ("Chennai", 13.0827, 80.2707),
    ("London", 51.5074, -0.1278),
    ("Sydney", -33.8688, 151.2093),
]


def v_house(v, graha):
    return v.house(graha)


# Candidate rules that survived fitting. Named so a survivor can be read off.
DARIDRA_CANDIDATES = {
    "classical: 11th lord in dusthana": lambda v: v.house(v.lord_of_house(11)) in (6, 8, 12),
    "lord4@4 OR h6empty": lambda v: v.house(v.lord_of_house(4)) == 4 or not v.occupants(6),
    "lord7@10 OR lord12_dig": lambda v: v.house(v.lord_of_house(7)) == 10
    or v.dignified(v.lord_of_house(12)),
    "lord8@9 OR h8empty": lambda v: v.house(v.lord_of_house(8)) == 9 or not v.occupants(8),
    "lord11@6 OR h6empty": lambda v: v.house(v.lord_of_house(11)) == 6 or not v.occupants(6),
    "Sun@11 OR lord12_dig": lambda v: v.house("Sun") == 11
    or v.dignified(v.lord_of_house(12)),
    "Rahu@8 OR h8empty": lambda v: v.house("Rahu") == 8 or not v.occupants(8),
    "Ketu@2 OR h8empty": lambda v: v.house("Ketu") == 2 or not v.occupants(8),
    "h6empty OR h8empty": lambda v: not v.occupants(6) or not v.occupants(8),
    "h6empty OR Venus_dig": lambda v: not v.occupants(6) or v.dignified("Venus"),
    "h6empty OR Saturn_dig": lambda v: not v.occupants(6) or v.dignified("Saturn"),
    "h6empty OR lord4_dig": lambda v: not v.occupants(6) or v.dignified(v.lord_of_house(4)),
    "h6empty OR lord12_dig": lambda v: not v.occupants(6)
    or v.dignified(v.lord_of_house(12)),
    "Mercury_dig OR lord12_dig": lambda v: v.dignified("Mercury")
    or v.dignified(v.lord_of_house(12)),
}


def _raja_pairs(v, kendras=(1, 4, 7, 10), trikonas=(1, 5, 9)):
    return [
        (a, b)
        for a in {v.lord_of_house(h) for h in kendras}
        for b in {v.lord_of_house(h) for h in trikonas}
        if a != b
    ]


RAJA_CANDIDATES = {
    "conjunction, mutual aspect or yogakaraka": lambda v: yogas.raja_yoga(v).present,
    "conjunction only": lambda v: any(v.in_same_sign(a, b) for a, b in _raja_pairs(v)),
    "conjunction or exchange": lambda v: any(
        v.in_same_sign(a, b)
        or (v.lord_of_house(v.house(a)) == b and v.lord_of_house(v.house(b)) == a)
        for a, b in _raja_pairs(v)
    ),
    "conjunction or one-way aspect": lambda v: any(
        v.in_same_sign(a, b) or v.aspects(a, v.house(b)) or v.aspects(b, v.house(a))
        for a, b in _raja_pairs(v)
    ),
    "conjunction or mutual aspect, no yogakaraka": lambda v: any(
        v.in_same_sign(a, b)
        or (v.aspects(a, v.house(b)) and v.aspects(b, v.house(a)))
        for a, b in _raja_pairs(v)
    ),
}

FAMILIES = {"Daridra Yoga": DARIDRA_CANDIDATES, "Raja Yoga": RAJA_CANDIDATES}


def candidates():
    for year in range(1952, 2016, 2):
        moment = datetime(year, 2, 8)
        while moment.year == year:
            for hour in (3, 9, 14, 19):
                for place, latitude, longitude in PLACES:
                    yield place, latitude, longitude, moment.replace(hour=hour, minute=41)
            moment += timedelta(days=53)


def signature(view) -> dict[str, tuple[bool, ...]]:
    return {
        family: tuple(bool(rule(view)) for rule in rules.values())
        for family, rules in FAMILIES.items()
    }


def propose() -> list[dict]:
    print("Scanning for charts that split the surviving rules...")
    pool = []
    for place, latitude, longitude, moment in candidates():
        try:
            chart = build(
                BirthData(moment.year, moment.month, moment.day, moment.hour,
                          moment.minute, 0, latitude, longitude),
                vargas=["D1"], dasha_depth=1,
            )
        except Exception:
            continue
        view = yogas.ChartView(chart)
        offset = chart["input"]["utc_offset_hours"]
        sign = "+" if offset >= 0 else "-"
        hours, minutes = divmod(round(abs(offset) * 60), 60)
        pool.append({
            "place": place, "latitude": latitude, "longitude": longitude,
            "local": moment.isoformat(),
            "datetime": moment.strftime("%Y-%m-%dT%H:%M:%S")
            + f"{sign}{hours:02d}:{minutes:02d}",
            "lagna": chart["lagna"]["sign_en"],
            "signature": signature(view),
        })
    print(f"  {len(pool):,} candidates")

    # Greedily pick charts that maximise the number of candidate pairs separated.
    alive = {family: list(rules) for family, rules in FAMILIES.items()}
    chosen: list[dict] = []
    for _ in range(CHARTS_PER_ROUND):
        best, best_score = None, -1
        for entry in pool:
            score = 0
            for family in FAMILIES:
                bits = entry["signature"][family]
                indices = [list(FAMILIES[family]).index(n) for n in alive[family]]
                votes = [bits[i] for i in indices]
                # A perfectly balanced split is the most informative.
                score += min(sum(votes), len(votes) - sum(votes))
            if score > best_score:
                best, best_score = entry, score
        if best is None or best_score == 0:
            break
        chosen.append(best)
        pool.remove(best)
        print(f"  {best['local'][:10]} {best['place']:8} lagna {best['lagna']:12} "
              f"splits {best_score}")
    return chosen


def verify(chosen: list[dict]) -> int:
    print(f"\nVerifying {len(chosen)} charts ({len(chosen) * 200} credits)\n")
    observations = []
    for entry in chosen:
        payload = fetch("yoga", {
            "ayanamsa": 1,
            "coordinates": f"{entry['latitude']},{entry['longitude']}",
            "datetime": entry["datetime"],
        })
        theirs = {}
        for group in payload["data"]["yoga_details"]:
            for item in group.get("yoga_list", []):
                theirs[item["name"]] = item["has_yoga"]
        observations.append((entry, theirs))
        print(f"  {entry['local'][:10]} {entry['place']:8} "
              + "  ".join(f"{k.split()[0]}={'T' if theirs[k] else '.'}" for k in FAMILIES))

    print()
    for family, rules in FAMILIES.items():
        expected = [t[family] for _, t in observations]
        print(f"=== {family} ===")
        print(f"  prokerala: {''.join('T' if e else '.' for e in expected)}")
        survivors = []
        for name in rules:
            index = list(rules).index(name)
            got = [e["signature"][family][index] for e, _ in observations]
            hits = sum(g == x for g, x in zip(got, expected))
            mark = "  <-- SURVIVES" if hits == len(expected) else ""
            print(f"  {''.join('T' if g else '.' for g in got)}  {hits:>2}/{len(expected)}"
                  f"  {name}{mark}")
            if hits == len(expected):
                survivors.append(name)
        print(f"  survivors: {survivors or 'none - all candidates eliminated'}")
    return 0


def main() -> int:
    if OUTPUT.exists() and "--verify" in sys.argv:
        chosen = json.loads(OUTPUT.read_text())["charts"]
    else:
        chosen = propose()
        OUTPUT.write_text(json.dumps({"charts": chosen}, indent=2))
        print(f"\nwrote {OUTPUT} ({len(chosen) * 200} credits to verify)")
        if "--verify" not in sys.argv:
            print("re-run with --verify to spend them")
            return 0
    return verify(chosen)


if __name__ == "__main__":
    raise SystemExit(main())
