"""Work out Prokerala's yoga rules from the cached verification responses.

Purely offline: it replays the charts through our engine and compares against
the responses already cached by against_prokerala_yogas.py. Costs nothing, so
hypotheses can be tried freely until one fits every chart.

    python validation/diagnose_yogas.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
from astro_engine import yogas  # noqa: E402
from astro_engine.chart import BirthData, build  # noqa: E402
from validation.against_prokerala import fetch  # noqa: E402

CHARTS = Path("validation/yoga_charts.json")
NODES = ("Rahu", "Ketu")


def load():
    plan = json.loads(CHARTS.read_text())
    rows = []
    for entry in plan["charts"]:
        year, month, rest = entry["local"].split("-", 2)
        day, clock = rest.split("T")
        hour, minute, *_ = clock.split(":")
        chart = build(
            BirthData(int(year), int(month), int(day), int(hour), int(minute), 0,
                      entry["latitude"], entry["longitude"]),
            vargas=["D1"], dasha_depth=1,
        )
        payload = fetch("yoga", {
            "ayanamsa": 1,
            "coordinates": f"{entry['latitude']},{entry['longitude']}",
            "datetime": entry["datetime"],
        })
        theirs = {}
        for group in payload["data"]["yoga_details"]:
            for item in group.get("yoga_list", []):
                theirs[item["name"]] = item["has_yoga"]
        rows.append((entry, chart, yogas.ChartView(chart), theirs))
    return rows


def try_rules(rows, yoga_name, hypotheses):
    """Score each candidate rule against every chart."""
    print(f"\n=== {yoga_name} ===")
    expected = [t[yoga_name] for _, _, _, t in rows if yoga_name in t]
    print(f"  prokerala says: {''.join('T' if e else '.' for e in expected)}")
    for label, rule in hypotheses.items():
        got = []
        for _, chart, view, _ in rows:
            try:
                got.append(bool(rule(view, chart)))
            except Exception:
                got.append(None)
        hits = sum(1 for g, e in zip(got, expected) if g == e)
        flag = "  <-- FITS" if hits == len(expected) else ""
        print(f"  {''.join('T' if g else '.' if g is not None else '?' for g in got)}"
              f"  {hits:>2}/{len(expected)}  {label}{flag}")


def moon_neighbours(view, exclude_sun=True):
    skip = set(NODES) | ({"Sun"} if exclude_sun else set()) | {"Moon"}
    house = view.house("Moon")
    second = [g for g in view.occupants(house % 12 + 1) if g not in skip]
    twelfth = [g for g in view.occupants((house - 2) % 12 + 1) if g not in skip]
    with_moon = [g for g in view.occupants(house) if g not in skip]
    return second, twelfth, with_moon


def main() -> int:
    rows = load()
    print(f"loaded {len(rows)} charts (all cached, no credits spent)")

    try_rules(rows, "Kemadruma Yoga", {
        "no planet in 2nd/12th, none with Moon (current)":
            lambda v, c: not any(moon_neighbours(v)),
        "no planet in 2nd/12th (ignore conjunction)":
            lambda v, c: not (moon_neighbours(v)[0] or moon_neighbours(v)[1]),
        "no planet in 2nd/12th, Sun counted":
            lambda v, c: not (moon_neighbours(v, False)[0] or moon_neighbours(v, False)[1]),
        "nothing with Moon only":
            lambda v, c: not moon_neighbours(v)[2],
    })

    try_rules(rows, "Daridra Yoga", {
        "11th lord in dusthana (current)":
            lambda v, c: v.house(v.lord_of_house(11)) in (6, 8, 12),
        "2nd lord in 12th":
            lambda v, c: v.house(v.lord_of_house(2)) == 12,
        "lagna lord in dusthana":
            lambda v, c: v.house(v.lord_of_house(1)) in (6, 8, 12),
        "11th lord in dusthana OR 2nd lord in 12th":
            lambda v, c: v.house(v.lord_of_house(11)) in (6, 8, 12)
            or v.house(v.lord_of_house(2)) == 12,
        "any of 2nd/11th lord in 6/8/12":
            lambda v, c: v.house(v.lord_of_house(2)) in (6, 8, 12)
            or v.house(v.lord_of_house(11)) in (6, 8, 12),
        "lord of 11th in 6/8/12 AND lagna lord weak":
            lambda v, c: v.house(v.lord_of_house(11)) in (6, 8, 12)
            and not v.dignified(v.lord_of_house(1)),
    })

    try_rules(rows, "Kamal Yoga", {
        "all 7 grahas in kendras (current)":
            lambda v, c: {v.house(g) for g in yogas.SEVEN_GRAHAS} <= {1, 4, 7, 10},
        "all 7 in kendras AND all four occupied":
            lambda v, c: {v.house(g) for g in yogas.SEVEN_GRAHAS} == {1, 4, 7, 10},
        "all 7 in kendras from Moon":
            lambda v, c: {v.house_from(g, "Moon") for g in yogas.SEVEN_GRAHAS}
            <= {1, 4, 7, 10},
    })

    try_rules(rows, "Raja Yoga", {
        "kendra-trikona link or yogakaraka (current)":
            lambda v, c: yogas.raja_yoga(v).present,
        "conjunction only":
            lambda v, c: any(
                v.in_same_sign(a, b)
                for a in {v.lord_of_house(h) for h in (1, 4, 7, 10)}
                for b in {v.lord_of_house(h) for h in (1, 5, 9)} if a != b
            ),
        "conjunction or exchange, no aspects":
            lambda v, c: any(
                v.in_same_sign(a, b)
                or (v.lord_of_house(v.house(a)) == b and v.lord_of_house(v.house(b)) == a)
                for a in {v.lord_of_house(h) for h in (1, 4, 7, 10)}
                for b in {v.lord_of_house(h) for h in (1, 5, 9)} if a != b
            ),
        "conjunction only, excluding the lagna lord":
            lambda v, c: any(
                v.in_same_sign(a, b)
                for a in {v.lord_of_house(h) for h in (4, 7, 10)}
                for b in {v.lord_of_house(h) for h in (5, 9)} if a != b
            ),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
