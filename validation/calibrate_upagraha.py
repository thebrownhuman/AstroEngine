"""Recover Prokerala's upagraha part table by measurement.

The classical texts disagree about which eighth of the day each upagraha
occupies and where inside it the point is taken, so the table is measured
instead of assumed: for each sample we invert Prokerala's longitude back into
the moment the Lagna held it, then express that moment as a fraction of the
day or night span. The answers come out on exact eighths and half-eighths.

    python validation/calibrate_upagraha.py

Cost: 30 credits per sample, cached afterwards.
"""

from __future__ import annotations

import sys
from datetime import datetime

sys.path.insert(0, ".")
from astro_engine.ephemeris import (  # noqa: E402
    SiderealSky, julian_day, sun_rise_set,
)
from astro_engine.geo import to_utc  # noqa: E402
from astro_engine.upagraha import TIME_DERIVED, WEEKDAY_LORDS  # noqa: E402
from validation.against_prokerala import fetch  # noqa: E402

DELHI = (28.6139, 77.2090)

# Midday and late-evening births, so the Vedic vara is the civil weekday and
# the day/night classification is unambiguous.
SAMPLES = [
    ("Mon day", datetime(1990, 1, 15, 12, 0), *DELHI, "+05:30"),
    ("Wed day", datetime(1990, 1, 17, 12, 0), *DELHI, "+05:30"),
    ("Sat day", datetime(1990, 1, 20, 12, 0), *DELHI, "+05:30"),
    ("Mon night", datetime(1990, 1, 15, 22, 0), *DELHI, "+05:30"),
    ("Wed night", datetime(1990, 1, 17, 22, 0), *DELHI, "+05:30"),
]


def measure(moment: datetime, lat: float, lon: float, tz: str) -> tuple[int, bool, dict]:
    utc, _ = to_utc(moment, lat, lon, None)
    jd = julian_day(utc)
    solar = sun_rise_set(jd, lat, lon, convention="geometric")
    by_night = jd >= solar["sunset_jd"]
    start, end = ((solar["sunset_jd"], solar["next_sunrise_jd"]) if by_night
                  else (solar["sunrise_jd"], solar["sunset_jd"]))
    vara = (moment.weekday() + 1) % 7

    theirs = fetch("upagraha-position", {
        "ayanamsa": 1, "coordinates": f"{lat},{lon}",
        "datetime": moment.strftime("%Y-%m-%dT%H:%M:%S") + tz,
    })["data"]["upagraha_position"]
    longitudes = {u["name"]: u["longitude"] for u in theirs}

    def ascendant(jd_ut: float) -> float:
        return SiderealSky(jd_ut).angles(lat, lon)["ascendant"].longitude

    parts = {}
    for name in TIME_DERIVED:
        lo, hi = start, end
        for _ in range(64):
            mid = (lo + hi) / 2
            if ((ascendant(mid) - longitudes[name] + 180.0) % 360.0 - 180.0) < 0:
                lo = mid
            else:
                hi = mid
        parts[name] = ((lo + hi) / 2 - start) / (end - start) * 8.0
    return vara, by_night, parts


def main() -> int:
    print(f"{'sample':12} {'vara':10} {'span':6} " +
          " ".join(f"{n[:9]:>9}" for n in TIME_DERIVED))
    rows = []
    for label, moment, lat, lon, tz in SAMPLES:
        vara, by_night, parts = measure(moment, lat, lon, tz)
        rows.append((label, vara, by_night, parts))
        print(f"{label:12} {WEEKDAY_LORDS[vara]:10} {'night' if by_night else 'day':6} " +
              " ".join(f"{parts[n]:9.4f}" for n in TIME_DERIVED))

    # Offset of each measured part from the plain weekday-lord rotation.
    print("\noffset from the lord rotation (index of the part, minus rotation index):")
    from astro_engine.upagraha import PART_RULER
    for label, vara, by_night, parts in rows:
        offsets = []
        for name in TIME_DERIVED:
            rotation = (WEEKDAY_LORDS.index(PART_RULER[name]) - vara) % 7
            offsets.append(f"{(int(parts[name]) - rotation) % 8:9d}")
        print(f"{label:12} {'night' if by_night else 'day':6} " + " ".join(offsets))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
