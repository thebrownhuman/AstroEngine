"""Fetch Prokerala answers for every Vedic endpoint the engine has not been
checked against widely enough.

Some endpoints had never been fetched at all (KP significators, sudarshana
chakra, chandrashtama, papasamyam-check, porutham, nakshatra porutham,
anandadi and auspicious yoga); others rested on one to four births. This
fetches them over a set of births chosen to stress the engine: both
hemispheres, DST on and off, high latitude, 1850 to 2150, times either side of
midnight, and moments where the Moon or the lagna sits within a few arcminutes
of a boundary.

Jobs are queued birth by birth, so if the credits run out part way every
endpoint still has its first few births. Everything lands in the shared cache;
the comparison scripts read it from there.

    python validation/sweep_coverage.py            # fetch
    python validation/sweep_coverage.py --plan     # list jobs and credits only
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, ".")
from astro_engine.ephemeris import SiderealScanner, julian_day  # noqa: E402
from validation.parallel_fetch import cache_path, run  # noqa: E402

LAHIRI, KP = 1, 5
NAKSHATRA_ARC = 360 / 27

# (label, local time, latitude, longitude, IANA zone)
BASE_BIRTHS = [
    ("Delhi 1990", datetime(1990, 1, 15, 4, 30), 28.6139, 77.2090, "Asia/Kolkata"),
    ("Sydney 1956 DST", datetime(1956, 1, 15, 14, 10), -33.8688, 151.2093, "Australia/Sydney"),
    ("New York 2001 DST", datetime(2001, 7, 4, 23, 55), 40.7128, -74.0060, "America/New_York"),
    ("London 1988", datetime(1988, 11, 2, 23, 20), 51.5074, -0.1278, "Europe/London"),
    ("Reykjavik 1972", datetime(1972, 6, 21, 0, 5), 64.1466, -21.9426, "Atlantic/Reykjavik"),
    ("Buenos Aires 1965", datetime(1965, 9, 30, 6, 45), -34.6037, -58.3816, "America/Argentina/Buenos_Aires"),
    ("Cape Town 2010", datetime(2010, 3, 21, 12, 0), -33.9249, 18.4241, "Africa/Johannesburg"),
    ("Tokyo 1945", datetime(1945, 8, 15, 12, 0), 35.6762, 139.6503, "Asia/Tokyo"),
    ("Honolulu 2024", datetime(2024, 2, 29, 18, 30), 21.3069, -157.8583, "Pacific/Honolulu"),
    ("Kolkata 1901", datetime(1901, 1, 1, 0, 1), 22.5726, 88.3639, "Asia/Kolkata"),
    ("Chennai 1850", datetime(1850, 5, 10, 9, 15), 13.0827, 80.2707, "Asia/Kolkata"),
    ("Mumbai 2150", datetime(2150, 12, 31, 23, 59), 19.0760, 72.8777, "Asia/Kolkata"),
    ("Moscow 1980", datetime(1980, 4, 1, 3, 3), 55.7558, 37.6173, "Europe/Moscow"),
    ("Singapore 1999", datetime(1999, 12, 31, 23, 59), 1.3521, 103.8198, "Asia/Singapore"),
    ("Kathmandu 1985", datetime(1985, 10, 12, 16, 40), 27.7172, 85.3240, "Asia/Kathmandu"),
    ("Los Angeles 1969", datetime(1969, 7, 20, 13, 17), 34.0522, -118.2437, "America/Los_Angeles"),
]


def _offset(moment: datetime, zone: str) -> str:
    delta = moment.replace(tzinfo=ZoneInfo(zone)).utcoffset()
    minutes = int(delta.total_seconds() // 60)
    sign = "+" if minutes >= 0 else "-"
    minutes = abs(minutes)
    return f"{sign}{minutes // 60:02d}:{minutes % 60:02d}"


def _moon_on_boundary(start: datetime, zone: str) -> datetime:
    """First minute after `start` with the Moon within 2' past a nakshatra cusp."""
    scanner = SiderealScanner()
    from swisseph import MOON

    moment = start
    for _ in range(60 * 24 * 2):
        utc = moment - ZoneInfo(zone).utcoffset(moment)
        lon = scanner.longitude(julian_day(utc), MOON)
        if lon % NAKSHATRA_ARC < 2 / 60:
            return moment
        moment += timedelta(minutes=1)
    return start


def births() -> list[tuple[str, datetime, float, float, str]]:
    edge = []
    for label, moment, lat, lon, zone in [
        ("Delhi Moon cusp 1977", datetime(1977, 3, 1, 0, 0), 28.6139, 77.2090, "Asia/Kolkata"),
        ("Sydney Moon cusp 2015", datetime(2015, 8, 10, 0, 0), -33.8688, 151.2093, "Australia/Sydney"),
        ("Bengaluru Moon cusp 2004", datetime(2004, 11, 5, 0, 0), 12.9716, 77.5946, "Asia/Kolkata"),
    ]:
        edge.append((label, _moon_on_boundary(moment, zone), lat, lon, zone))
    return BASE_BIRTHS + edge


def _single(moment, lat, lon, zone, ayanamsa=LAHIRI) -> dict:
    return {"ayanamsa": ayanamsa, "coordinates": f"{lat},{lon}",
            "datetime": moment.strftime("%Y-%m-%dT%H:%M:%S") + _offset(moment, zone)}


# Endpoint -> (births to use, ayanamsa). Ordered cheapest-per-signal first.
SINGLE = [
    ("planet-position", 99, LAHIRI),
    ("mangal-dosha", 99, LAHIRI),
    ("kundli", 99, LAHIRI),
    ("kp-house-significator", 99, KP),
    ("kp-planet-significator", 99, KP),
    ("sudarshana-chakra", 99, LAHIRI),
    ("kp-planet-position", 12, KP),
    ("dasha-periods", 12, LAHIRI),
    ("planet-relationship", 12, LAHIRI),
    ("anandadi-yoga", 12, LAHIRI),
    ("auspicious-yoga", 12, LAHIRI),
    ("sarvashtakavarga", 8, LAHIRI),
]


def jobs() -> list[tuple[str, dict]]:
    people = births()
    out: list[tuple[str, dict]] = []
    for i, (_, moment, lat, lon, zone) in enumerate(people):
        for endpoint, limit, ayanamsa in SINGLE:
            if i < limit:
                out.append((endpoint, _single(moment, lat, lon, zone, ayanamsa)))
        if i < 8:
            out.append(("chandrashtama-periods", {
                **_single(moment, lat, lon, zone), "year": 2026,
            }))
        # Pair each person with the next one: girl = i, boy = i + 1.
        girl, boy = people[i], people[(i + 1) % len(people)]
        pair = {
            "ayanamsa": LAHIRI,
            "girl_coordinates": f"{girl[2]},{girl[3]}",
            "girl_dob": girl[1].strftime("%Y-%m-%dT%H:%M:%S") + _offset(girl[1], girl[4]),
            "boy_coordinates": f"{boy[2]},{boy[3]}",
            "boy_dob": boy[1].strftime("%Y-%m-%dT%H:%M:%S") + _offset(boy[1], boy[4]),
        }
        if i < 12:
            out.append(("papasamyam-check", pair))
            out.append(("porutham", {**pair, "system": "tamil"}))
            out.append(("porutham", {**pair, "system": "kerala"}))
    # Star-pair table: pada 4 is broken on their side (see README), so 1-3.
    for g in range(27):
        b = (g * 7 + 3) % 27
        out.append(("nakshatra-porutham", {
            "girl_nakshatra": g, "girl_nakshatra_pada": 1 + g % 3,
            "boy_nakshatra": b, "boy_nakshatra_pada": 1 + b % 3,
        }))
    return out


COST = {
    "planet-position": 30, "mangal-dosha": 30, "kundli": 50,
    "kp-house-significator": 100, "kp-planet-significator": 100,
    "sudarshana-chakra": 100, "kp-planet-position": 200, "dasha-periods": 200,
    "planet-relationship": 200, "anandadi-yoga": 200, "auspicious-yoga": 300,
    "sarvashtakavarga": 300, "chandrashtama-periods": 200,
    "papasamyam-check": 50, "porutham": 50, "nakshatra-porutham": 50,
}


def main() -> int:
    todo = jobs()
    missing = [j for j in todo if not cache_path(*j).exists()]
    credits = sum(COST[e] for e, _ in missing)
    print(f"{len(todo)} jobs, {len(missing)} not cached, ~{credits} credits")
    if "--plan" in sys.argv:
        for label, moment, *_ in births():
            print(f"  {label}: {moment}")
        return 0
    results = run(todo, "coverage sweep")
    failed = [(j[0], str(r)[:120]) for j, r in zip(todo, results) if isinstance(r, Exception)]
    for endpoint, error in failed:
        print(f"  FAILED {endpoint}: {error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
