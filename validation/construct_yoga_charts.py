"""Pick a small set of birth charts that exercises all 24 yogas.

Verification costs 200 credits per chart, so random charts are wasteful: rare
yogas like the Panchamahapurusha set would never fire. Instead we scan many
candidate birth moments with our own engine (free) and greedily choose the
smallest set that observes every yoga in BOTH states - present and absent.

A yoga only ever observed in one state is not really verified: a detector stuck
on False agrees with Prokerala on every chart where the yoga is genuinely
absent. The report flags any such gap.

    python validation/construct_yoga_charts.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, ".")
from astro_engine import yogas  # noqa: E402
from astro_engine.chart import BirthData, build  # noqa: E402

OUTPUT = Path("validation/yoga_charts.json")

# A spread of latitudes and timezones, so the Lagna and house layout vary.
PLACES = [
    ("Delhi", 28.6139, 77.2090),
    ("Chennai", 13.0827, 80.2707),
    ("London", 51.5074, -0.1278),
    ("Sydney", -33.8688, 151.2093),
]

# Scan across decades and hours: the Lagna turns through all twelve signs in a
# day, while the slow grahas move across years.
START_YEAR, END_YEAR = 1950, 2020
DAY_STEP = 37          # a prime-ish stride avoids sampling the same phase
HOURS = (2, 7, 11, 16, 20)

TARGET_CHARTS = 16

# Each (yoga, state) pair should be seen this many times. One observation is
# weak evidence: a detector stuck on False agrees with Prokerala on every chart
# where the yoga is genuinely absent.
REDUNDANCY = 3


def candidates():
    for year in range(START_YEAR, END_YEAR + 1, 3):
        moment = datetime(year, 1, 1)
        while moment.year == year:
            for hour in HOURS:
                for place, latitude, longitude in PLACES:
                    yield place, latitude, longitude, moment.replace(hour=hour, minute=17)
            moment += timedelta(days=DAY_STEP)


def observe(place: str, latitude: float, longitude: float, moment: datetime):
    chart = build(
        BirthData(moment.year, moment.month, moment.day, moment.hour, moment.minute, 0,
                  latitude, longitude),
        vargas=["D1"], dasha_depth=1,
    )
    found = yogas.detect(chart)
    # The engine treats the naive moment as local time at those coordinates, so
    # the offset sent to Prokerala has to match, DST and all.
    offset = chart["input"]["utc_offset_hours"]
    sign = "+" if offset >= 0 else "-"
    hours, minutes = divmod(round(abs(offset) * 60), 60)
    return {
        "place": place,
        "latitude": latitude,
        "longitude": longitude,
        "timezone": chart["input"]["timezone"],
        "datetime": moment.strftime("%Y-%m-%dT%H:%M:%S") + f"{sign}{hours:02d}:{minutes:02d}",
        "local": moment.isoformat(),
        "lagna": chart["lagna"]["sign_en"],
        "expected": {y.name: y.present for y in found},
    }


def main() -> int:
    print("Scanning candidate birth moments for yoga coverage...")
    all_names = [y.name for y in yogas.detect(
        build(BirthData(1990, 1, 15, 4, 30, 0, 28.6139, 77.2090), vargas=["D1"], dasha_depth=1)
    )]
    wanted = {(name, state) for name in all_names for state in (True, False)}

    pool = []
    for index, (place, latitude, longitude, moment) in enumerate(candidates()):
        try:
            pool.append(observe(place, latitude, longitude, moment))
        except Exception:
            continue
        if index % 2000 == 0 and index:
            print(f"  scanned {index:,}")
    print(f"  scanned {len(pool):,} charts total")

    # Greedy set cover, counting how many times each pair has been seen. Value a
    # pair only until it reaches REDUNDANCY, so later picks chase the gaps.
    chosen: list[dict] = []
    seen: dict[tuple[str, bool], int] = {pair: 0 for pair in wanted}

    def shortfall() -> int:
        return sum(max(0, REDUNDANCY - count) for count in seen.values())

    while len(chosen) < TARGET_CHARTS and shortfall() > 0:
        best, best_gain = None, 0
        for entry in pool:
            gain = sum(
                1 for pair in entry["expected"].items() if seen[pair] < REDUNDANCY
            )
            if gain > best_gain:
                best, best_gain = entry, gain
        if best is None:
            break
        chosen.append(best)
        for pair in best["expected"].items():
            seen[pair] += 1
        pool.remove(best)
        done = sum(1 for c in seen.values() if c >= REDUNDANCY)
        print(f"  chart {len(chosen):2}: {best['local'][:10]} {best['place']:8} "
              f"lagna {best['lagna']:12} +{best_gain} needed "
              f"({done}/{len(wanted)} pairs at x{REDUNDANCY})")

    covered = {pair for pair, count in seen.items() if count > 0}
    thin = sorted(pair for pair, count in seen.items() if 0 < count < REDUNDANCY)
    missing = sorted(wanted - covered)
    if thin:
        print(f"\nseen but fewer than {REDUNDANCY} times:")
        for name, state in thin:
            print(f"  {name} = {state}  (x{seen[(name, state)]})")
    print(f"\nselected {len(chosen)} charts, covering {len(covered)}/{len(wanted)} pairs")
    if missing:
        print("\nnever observed (cannot be verified in both states):")
        for name, state in missing:
            print(f"  {name} = {state}")

    OUTPUT.write_text(json.dumps({
        "charts": chosen,
        "coverage": {"observed": len(covered), "possible": len(wanted)},
        "unobserved": [{"yoga": n, "state": s} for n, s in missing],
        "observation_counts": {f"{n}|{s}": c for (n, s), c in seen.items()},
        "cost_credits": len(chosen) * 200,
    }, indent=2))
    print(f"\nwrote {OUTPUT}  (verification will cost {len(chosen) * 200} credits)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
