"""Recover the weekday tables behind Prokerala's muhurta endpoints.

Rahu Kaal, Yamaganda, Gulika Kaal and Dur Muhurat are all "the Nth slice of the
day", where N depends on the weekday and the texts disagree about the tables.
Rather than trust a table, this samples one chart per weekday and reports which
slice each period actually landed on, as an exact index.

Day is cut two ways: into eight parts (the kaal periods and the choghadiya) and
into fifteen muhurtas (Abhijit and Dur Muhurat). Both are measured.

    python validation/calibrate_muhurta.py

Cost: 100 credits per weekday (inauspicious 50 + choghadiya 50), cached after.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta

sys.path.insert(0, ".")
from astro_engine.constants import WEEKDAYS  # noqa: E402
from astro_engine.ephemeris import (  # noqa: E402
    jd_to_datetime, julian_day, sun_rise_set,
)
from validation.against_prokerala import fetch  # noqa: E402

LATITUDE, LONGITUDE = 28.6139, 77.2090
OFFSET = timedelta(hours=5.5)
TZ = "+05:30"

# Seven consecutive days, so every weekday is covered once.
FIRST = datetime(1990, 1, 14, 12, 0)
DAYS = [FIRST + timedelta(days=n) for n in range(7)]


def solar_for(day: datetime) -> tuple[datetime, datetime]:
    """Sunrise and sunset of that calendar date, in local time."""
    noon = julian_day(day - OFFSET)
    solar = sun_rise_set(noon, LATITUDE, LONGITUDE, convention="geometric")
    return (jd_to_datetime(solar["sunrise_jd"]) + OFFSET,
            jd_to_datetime(solar["sunset_jd"]) + OFFSET)


def slice_of(moment: datetime, sunrise: datetime, sunset: datetime, parts: int) -> float:
    width = (sunset - sunrise).total_seconds() / parts
    return (moment - sunrise).total_seconds() / width


def main() -> int:
    print(f"{'weekday':10} {'period':14} {'of 8':>9} {'of 15':>9}")
    for day in DAYS:
        sunrise, sunset = solar_for(day)
        params = {"ayanamsa": 1, "coordinates": f"{LATITUDE},{LONGITUDE}",
                  "datetime": day.strftime("%Y-%m-%dT%H:%M:%S") + TZ}
        weekday = WEEKDAYS[(day.weekday() + 1) % 7]

        for entry in fetch("inauspicious-period", params)["data"]["muhurat"]:
            for period in entry["period"]:
                start = datetime.fromisoformat(period["start"]).replace(tzinfo=None)
                print(f"{weekday:10} {entry['name']:14} "
                      f"{slice_of(start, sunrise, sunset, 8):9.4f} "
                      f"{slice_of(start, sunrise, sunset, 15):9.4f}")

        chogha = fetch("choghadiya", params)["data"]["muhurat"]
        day_names = [m["name"] for m in chogha if m["is_day"]]
        night_names = [m["name"] for m in chogha if not m["is_day"]]
        print(f"{weekday:10} choghadiya day   {day_names}")
        print(f"{weekday:10} choghadiya night {night_names}")
        print(f"{weekday:10} velas            "
              + str([(m["vela"], "day" if m["is_day"] else "night",
                      [c["start"] for c in chogha
                       if c["is_day"] == m["is_day"]].index(m["start"]))
                     for m in chogha if m["vela"]]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
