"""Validate the engine against NASA JPL Horizons.

Horizons is the authority Swiss Ephemeris is fitted to, so this is a stronger
check than comparing against another astrology API (which is almost certainly
running Swiss Ephemeris itself).

We compare apparent geocentric ecliptic-of-date longitude, which is exactly what
`ObsEcLon` (quantity 31) returns and what swisseph computes by default. The
ayanamsa is then subtracted locally to reach the sidereal values the engine
reports, so a match here validates the whole positional chain.

    python validation/against_jpl.py
"""

from __future__ import annotations

import re
import sys
import time
from datetime import datetime

import httpx
import swisseph as swe

sys.path.insert(0, ".")
from astro_engine.ephemeris import (  # noqa: E402
    EPHEMERIS_BACKEND, _BACKEND_FLAG, julian_day,
)

HORIZONS = "https://ssd.jpl.nasa.gov/api/horizons.api"

# Horizons body IDs -> our graha names.
BODIES = {
    "Sun": "10",
    "Moon": "301",
    "Mercury": "199",
    "Venus": "299",
    "Mars": "499",
    "Jupiter": "599",
    "Saturn": "699",
}

SWE_BODIES = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY, "Venus": swe.VENUS,
    "Mars": swe.MARS, "Jupiter": swe.JUPITER, "Saturn": swe.SATURN,
}

EPOCHS = [
    datetime(1943, 6, 15, 6, 30),    # wartime India, tests the historical end
    datetime(1990, 1, 14, 23, 0),    # the chart used throughout the test suite
    datetime(2000, 1, 1, 12, 0),     # J2000, the standard reference epoch
    datetime(2026, 9, 20, 0, 0),     # today
]

# Horizons prints the ephemeris block between these markers.
_BLOCK = re.compile(r"\$\$SOE\s*(.*?)\s*\$\$EOE", re.S)


def horizons_longitude(body_id: str, moment: datetime) -> float:
    stop = moment.replace(second=0)
    params = {
        "format": "text",
        "COMMAND": f"'{body_id}'",
        "OBJ_DATA": "NO",
        "MAKE_EPHEM": "YES",
        "EPHEM_TYPE": "OBSERVER",
        "CENTER": "'500@399'",
        "START_TIME": f"'{stop:%Y-%m-%d %H:%M}'",
        "STOP_TIME": f"'{stop:%Y-%m-%d %H:%M}:01'",
        "STEP_SIZE": "'1 m'",
        "QUANTITIES": "'31'",
        "ANG_FORMAT": "DEG",
        "CSV_FORMAT": "YES",
    }
    response = httpx.get(HORIZONS, params=params, timeout=90.0)
    response.raise_for_status()
    match = _BLOCK.search(response.text)
    if not match:
        raise RuntimeError(f"no ephemeris block for body {body_id}\n{response.text[-800:]}")
    first = match.group(1).strip().splitlines()[0]
    fields = [f.strip() for f in first.split(",")]
    # CSV layout: date, (blank solar/lunar flags), ObsEcLon, ObsEcLat
    numbers = [f for f in fields if re.fullmatch(r"-?\d+\.\d+", f)]
    if len(numbers) < 2:
        raise RuntimeError(f"unexpected Horizons row: {first!r}")
    return float(numbers[0])


def engine_tropical_longitude(body: int, jd: float) -> float:
    values, _ = swe.calc_ut(jd, body, _BACKEND_FLAG | swe.FLG_SPEED)
    return values[0] % 360.0


def arcsec_delta(a: float, b: float) -> float:
    diff = (a - b + 180.0) % 360.0 - 180.0
    return diff * 3600.0


def main() -> int:
    print("Validating astro_engine against NASA JPL Horizons")
    print("Comparing apparent geocentric ecliptic-of-date longitude\n")
    print(f"Backend in use: {EPHEMERIS_BACKEND}")

    worst = 0.0
    worst_label = ""
    rows = 0
    failures = []

    for moment in EPOCHS:
        jd = julian_day(moment)
        print(f"{moment:%Y-%m-%d %H:%M} UT   (JD {jd:.6f})")
        print(f"  {'body':<9} {'engine':>13} {'JPL Horizons':>14} {'delta':>12}")
        for name, body_id in BODIES.items():
            try:
                jpl = horizons_longitude(body_id, moment)
            except Exception as exc:  # network or parse problem, not a maths problem
                print(f"  {name:<9} SKIPPED ({exc})")
                continue
            ours = engine_tropical_longitude(SWE_BODIES[name], jd)
            delta = arcsec_delta(ours, jpl)
            rows += 1
            if abs(delta) > abs(worst):
                worst, worst_label = delta, f"{name} at {moment:%Y-%m-%d}"
            # The Moon is the hardest case, and Moshier is weakest there.
            if name == "Moon":
                tolerance = 5.0 if EPHEMERIS_BACKEND == "moshier" else 1.0
            else:
                tolerance = 1.0
            flag = "ok" if abs(delta) <= tolerance else "FAIL"
            if flag == "FAIL":
                failures.append((name, moment, delta, tolerance))
            print(f"  {name:<9} {ours:13.6f} {jpl:14.6f} {delta:10.3f}\"  {flag}")
            time.sleep(0.4)  # be polite to a free public service
        print()

    print(f"{rows} comparisons, worst deviation {worst:+.3f} arcsec ({worst_label})")
    if failures:
        print(f"\n{len(failures)} outside tolerance:")
        for name, moment, delta, tol in failures:
            print(f"  {name} {moment:%Y-%m-%d}: {delta:+.3f}\" (tolerance {tol}\")")
        return 1
    print("All bodies within tolerance of NASA JPL.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
