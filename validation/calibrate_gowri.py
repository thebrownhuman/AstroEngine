"""Recover the Gowri Nalla Neram, Disha Shool and Hora weekday tables.

Same method as calibrate_muhurta: one sample per weekday, read the sequence
straight off the live API rather than trusting a printed table.

    python validation/calibrate_gowri.py

Cost: 300 credits per weekday (gowri 100 + disha shool 100 + hora 200).
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta

sys.path.insert(0, ".")
from astro_engine.constants import WEEKDAYS  # noqa: E402
from astro_engine.muhurta import solar_day  # noqa: E402
from validation.against_prokerala import fetch  # noqa: E402

LATITUDE, LONGITUDE = 28.6139, 77.2090
OFFSET_HOURS = 5.5
TZ = "+05:30"
DAYS = [datetime(1990, 1, 14, 12, 0) + timedelta(days=n) for n in range(7)]


def main() -> int:
    for day in DAYS:
        params = {"ayanamsa": 1, "coordinates": f"{LATITUDE},{LONGITUDE}",
                  "datetime": day.strftime("%Y-%m-%dT%H:%M:%S") + TZ}
        solar = solar_day(day, LATITUDE, LONGITUDE, OFFSET_HOURS)
        weekday = WEEKDAYS[(solar["sunrise"].weekday() + 1) % 7]

        gowri = fetch("gowri-nalla-neram", params)["data"]["muhurat"]
        print(f"{weekday:10} gowri day   "
              + str([(m["id"], m["name"]) for m in gowri if m["is_day"]]))
        print(f"{weekday:10} gowri night "
              + str([(m["id"], m["name"]) for m in gowri if not m["is_day"]]))

        shool = fetch("disha-shool", params)["data"]["disha_shool"]
        start = datetime.fromisoformat(shool["start"]).replace(tzinfo=None)
        end = datetime.fromisoformat(shool["end"]).replace(tzinfo=None)
        print(f"{weekday:10} disha       {shool['direction']:6} {shool['remedy']:10} "
              f"from sunrise {(start - solar['sunrise']).total_seconds():+.0f}s "
              f"for {(end - start).total_seconds():.0f}s")

        hora = fetch("hora", params)["data"]["hora_timing"]
        print(f"{weekday:10} hora day    "
              + str([h["hora"]["name"] for h in hora if h["is_day"]][:4]) + " ...")
        print(f"{weekday:10} hora types  "
              + str(sorted({(h["hora"]["name"], h["type"]) for h in hora})))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
