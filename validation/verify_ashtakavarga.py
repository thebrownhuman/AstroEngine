"""Ashtakavarga parity against the live Prokerala API.

One /sarvashtakavarga call is worth 84 checks: its prastara grid carries every
planet's bindu count in every sign, so a single response validates all seven
contribution tables at once. The per-planet /ashtakavarga call is then only
needed for the two reduction views, trikona and ekaadhipatya.

    python validation/verify_ashtakavarga.py

Cost when uncached: 300 per sarvashtakavarga chart, 200 per ashtakavarga planet.
"""

from __future__ import annotations

import sys
from datetime import datetime

sys.path.insert(0, ".")
from astro_engine import ashtakavarga as av  # noqa: E402
from astro_engine.chart import BirthData, build  # noqa: E402
from astro_engine.constants import SIGNS  # noqa: E402
from validation.against_prokerala import fetch  # noqa: E402

CHARTS = [
    ("Delhi 1990", datetime(1990, 1, 15, 4, 30), 28.6139, 77.2090, "+05:30"),
]

# Which planets to pull the reduction views for. These three between them
# exercise every ekadhipatya branch this chart can reach: Saturn reduces
# nothing, Mars hits the both-signs-empty-and-equal rule that zeroes a pair,
# and Venus hits the one-sign-occupied rule that levels down to the lesser.
REDUCTION_PLANETS = {
    "Delhi 1990": [("Saturn", 6), ("Mars", 4), ("Venus", 3)],
}


def sign_of(house_block: dict) -> int:
    return SIGNS.index(house_block["rasi"]["name"])


def run() -> int:
    failures: list[str] = []
    checks = 0

    for label, moment, lat, lon, tz in CHARTS:
        iso = moment.strftime("%Y-%m-%dT%H:%M:%S") + tz
        params = {"ayanamsa": 1, "coordinates": f"{lat},{lon}", "datetime": iso}
        chart = build(
            BirthData(moment.year, moment.month, moment.day,
                      moment.hour, moment.minute, 0, lat, lon),
            vargas=["D1"], dasha_depth=1,
        )
        mine = av.compute(chart)
        print(f"\n--- {label} ---")

        # --- sarvashtakavarga: the whole bindu grid in one response ----------
        theirs = fetch("sarvashtakavarga", params)["data"]["sarvashtakavarga"]
        for house in theirs["prastara"]["houses"]:
            sign = sign_of(house)
            for entry in house["planets"]:
                name = entry["planet"]["name"]
                ours = mine["ashtakavarga"][name]["by_sign"][sign]
                checks += 1
                if ours != entry["score"]:
                    failures.append(
                        f"{label} BAV {name} in {SIGNS[sign]}: {ours} vs {entry['score']}"
                    )
            checks += 1
            if mine["sarvashtakavarga"]["by_sign"][sign] != house["score"]:
                failures.append(
                    f"{label} SAV {SIGNS[sign]}: "
                    f"{mine['sarvashtakavarga']['by_sign'][sign]} vs {house['score']}"
                )
        print(f"  sarvashtakavarga: {len(theirs['prastara']['houses'])} houses, "
              f"total {theirs['prastara']['score']} vs {mine['sarvashtakavarga']['total']}")

        # --- one planet's reduction views ------------------------------------
        for planet, planet_id in REDUCTION_PLANETS[label]:
          single = fetch("ashtakavarga", {**params, "planet": planet_id})
          block = single["data"]["ashtakavarga"]
          for view in ("prastara", "trikona", "ekaadhipatya"):
              if view not in block:
                  print(f"  {view}: absent from response")
                  continue
              for house in block[view]["houses"]:
                  sign = sign_of(house)
                  ours = mine["ashtakavarga"][planet][view]["houses"]
                  ours_score = next(
                      h["score"] for h in ours if h["rasi"]["index"] == sign
                  )
                  checks += 1
                  if ours_score != house["score"]:
                      failures.append(
                          f"{label} {planet} {view} {SIGNS[sign]}: "
                          f"{ours_score} vs {house['score']}"
                      )
              print(f"  {planet} {view:13} total "
                    f"{mine['ashtakavarga'][planet][view]['score']} vs {block[view]['score']}")

    print(f"\n{checks - len(failures)}/{checks} ashtakavarga checks pass")
    for line in failures[:40]:
        print(f"  {line}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())
