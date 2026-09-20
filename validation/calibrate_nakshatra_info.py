"""Collect the per-nakshatra reference block Prokerala's birth-details returns.

Deity, symbol, animal sign, gemstone and the rest are static per nakshatra, so
twenty-seven births -- one with the Moon in each -- pull the whole table. It is
printed as a Python literal ready to paste into constants.py.

    python validation/calibrate_nakshatra_info.py

Cost: 50 credits per nakshatra, 1,350 in total. Fetched across every live
app at once, so it finishes in about a minute.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta

sys.path.insert(0, ".")
from astro_engine.chart import BirthData, build  # noqa: E402
from astro_engine.constants import NAKSHATRAS  # noqa: E402
from validation.parallel_fetch import run  # noqa: E402

DELHI = (28.6139, 77.2090)
TZ = "+05:30"
FIELDS = ("deity", "ganam", "symbol", "animal_sign", "nadi", "color",
          "best_direction", "syllables", "birth_stone", "gender", "planet",
          "enemy_yoni")


def dates_covering_every_nakshatra() -> dict[int, datetime]:
    """One noon birth per nakshatra. The Moon walks through all 27 in a month."""
    found: dict[int, datetime] = {}
    moment = datetime(1990, 1, 1, 12, 0)
    while len(found) < 27 and moment < datetime(1990, 4, 1):
        chart = build(
            BirthData(moment.year, moment.month, moment.day, 12, 0, 0, *DELHI),
            vargas=["D1"], dasha_depth=1,
        )
        found.setdefault(chart["grahas"]["Moon"]["nakshatra_index"], moment)
        moment += timedelta(days=1)
    return found


def main() -> int:
    dates = dates_covering_every_nakshatra()
    missing = [n for n in range(27) if n not in dates]
    if missing:
        print(f"no date found for {[NAKSHATRAS[n] for n in missing]}")

    order = sorted(dates)
    answers = run([
        ("birth-details", {
            "ayanamsa": 1, "coordinates": f"{DELHI[0]},{DELHI[1]}",
            "datetime": dates[index].strftime("%Y-%m-%dT%H:%M:%S") + TZ,
        })
        for index in order
    ], "nakshatra attributes")

    collected: dict[int, dict] = {}
    for index, answer in zip(order, answers):
        if isinstance(answer, Exception):
            print(f"  {NAKSHATRAS[index]}: {str(answer)[:100]}")
            continue
        data = answer["data"]
        if data["nakshatra"]["id"] != index:
            print(f"  {NAKSHATRAS[index]}: got {data['nakshatra']['name']} instead")
            continue
        collected[index] = {key: data["additional_info"][key] for key in FIELDS}
        print(f"  {NAKSHATRAS[index]:18} {data['additional_info']['deity']}")

    print("\nNAKSHATRA_ATTRIBUTES = {")
    for index in range(27):
        block = collected.get(index)
        if block is None:
            print(f"    # {index}: {NAKSHATRAS[index]} not collected")
            continue
        print(f"    {index}: {json.dumps(block, ensure_ascii=False)},")
    print("}")
    print(f"\ncollected {len(collected)}/27")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
