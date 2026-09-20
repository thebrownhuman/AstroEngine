"""Ashtakoot parity against the live /kundli-matching endpoint.

Each basic response carries sixteen koot labels -- eight for each partner --
plus the total, so it validates the classification tables and the scoring at
once for fifty credits. Pairs are chosen to spread across varna, gana, nadi
and bhakoot combinations rather than to be realistic.

    python validation/verify_matching.py
    python validation/verify_matching.py --advanced   # per-koot points, 200 each
"""

from __future__ import annotations

import sys
from datetime import datetime

sys.path.insert(0, ".")
from astro_engine import matching  # noqa: E402
from astro_engine.chart import BirthData, build  # noqa: E402
from validation.against_prokerala import fetch  # noqa: E402

DELHI = (28.6139, 77.2090)
TZ = "+05:30"

# (label, boy birth, girl birth). Spread over years and months so the Moons
# land in many different signs and nakshatras.
PAIRS = [
    ("A", datetime(1990, 1, 15, 4, 30), datetime(1992, 6, 3, 11, 15)),
    ("B", datetime(1985, 9, 21, 18, 40), datetime(1988, 2, 14, 7, 5)),
    ("C", datetime(1979, 4, 7, 22, 10), datetime(1983, 11, 30, 14, 50)),
    ("D", datetime(1995, 7, 19, 3, 25), datetime(1997, 12, 8, 9, 35)),
    ("E", datetime(1972, 3, 2, 16, 0), datetime(1975, 8, 25, 20, 45)),
    ("F", datetime(2000, 10, 11, 6, 20), datetime(2001, 5, 17, 13, 10)),
    ("G", datetime(1968, 12, 24, 23, 55), datetime(1970, 1, 9, 5, 40)),
    ("H", datetime(1993, 2, 28, 12, 30), datetime(1994, 9, 14, 17, 20)),
    ("I", datetime(1987, 6, 6, 8, 45), datetime(1989, 3, 21, 21, 15)),
    ("J", datetime(2004, 8, 30, 15, 5), datetime(2006, 4, 2, 10, 55)),
    # Chosen by search rather than by hand, to reach vasya, gana and yoni
    # matrix cells the ten above never touch.
    ("K", datetime(1990, 1, 1, 6, 0), datetime(1990, 1, 22, 6, 0)),
    ("L", datetime(1990, 1, 2, 18, 0), datetime(1990, 1, 4, 18, 0)),
    ("M", datetime(1990, 1, 3, 6, 0), datetime(1990, 1, 8, 6, 0)),
    ("N", datetime(1990, 1, 3, 18, 0), datetime(1990, 1, 1, 6, 0)),
    ("O", datetime(1990, 1, 4, 6, 0), datetime(1990, 1, 15, 6, 0)),
    ("P", datetime(1990, 1, 4, 18, 0), datetime(1990, 1, 18, 18, 0)),
    ("Q", datetime(1990, 1, 5, 6, 0), datetime(1990, 1, 22, 6, 0)),
    ("R", datetime(1990, 1, 5, 18, 0), datetime(1990, 1, 1, 6, 0)),
    ("S", datetime(1990, 1, 6, 6, 0), datetime(1990, 1, 4, 18, 0)),
    ("T", datetime(1990, 1, 6, 18, 0), datetime(1990, 1, 15, 6, 0)),
    ("U", datetime(1990, 1, 7, 6, 0), datetime(1990, 1, 22, 6, 0)),
    ("V", datetime(1990, 1, 14, 6, 0), datetime(1990, 1, 8, 6, 0)),
]

KOOT_KEYS = ["varna", "vasya", "tara", "yoni", "graha_maitri",
             "gana", "bhakoot", "nadi"]


def chart_for(moment: datetime) -> dict:
    return build(
        BirthData(moment.year, moment.month, moment.day,
                  moment.hour, moment.minute, 0, *DELHI),
        vargas=["D1"], dasha_depth=1,
    )


def stamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%S") + TZ


def main(advanced: bool = False) -> int:
    endpoint = "kundli-matching/advanced" if advanced else "kundli-matching"
    checks = 0
    failures: list[str] = []

    for label, boy_birth, girl_birth in PAIRS:
        mine = matching.compute(chart_for(boy_birth), chart_for(girl_birth))
        theirs = fetch(endpoint, {
            "ayanamsa": 1,
            "boy_coordinates": f"{DELHI[0]},{DELHI[1]}",
            "boy_dob": stamp(boy_birth),
            "girl_coordinates": f"{DELHI[0]},{DELHI[1]}",
            "girl_dob": stamp(girl_birth),
        })["data"]

        for who in ("boy_info", "girl_info"):
            for key in KOOT_KEYS:
                checks += 1
                ours = mine[who]["koot"][key]
                other = theirs[who]["koot"][key]
                if ours != other:
                    failures.append(f"{label} {who} {key}: {ours} vs {other}")
            checks += 1
            if mine[who]["nakshatra"]["name"] != theirs[who]["nakshatra"]["name"]:
                failures.append(
                    f"{label} {who} nakshatra: {mine[who]['nakshatra']['name']} "
                    f"vs {theirs[who]['nakshatra']['name']}"
                )

        checks += 1
        ours_total = mine["guna_milan"]["total_points"]
        their_total = theirs["guna_milan"]["total_points"]
        if abs(ours_total - their_total) > 1e-9:
            failures.append(f"{label} total: {ours_total} vs {their_total}")

        if advanced:
            for ours, other in zip(mine["guna_milan"]["guna"],
                                   theirs["guna_milan"]["guna"]):
                checks += 1
                if abs(ours["obtained_points"] - other["obtained_points"]) > 1e-9:
                    failures.append(
                        f"{label} {other['name']}: {ours['obtained_points']} "
                        f"vs {other['obtained_points']}"
                    )
        print(f"  {label}: {ours_total:5.2f} vs {their_total:5.2f}")

    print(f"\n{checks - len(failures)}/{checks} matching checks pass")
    for line in failures[:60]:
        print(f"  {line}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main("--advanced" in sys.argv))
