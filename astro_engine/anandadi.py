"""Anandadi yoga: the weekday read against the Moon's nakshatra.

Twenty-eight yogas, Ananda first, on the twenty-eight star scheme that puts
Abhijit between Uttara Ashadha and Shravana. Each weekday starts the count at
its own star -- Sunday at Ashwini, then every fourth star -- so the yoga is
(star - 4 x weekday) mod 28.

A date's yogas are those of every nakshatra the Moon occupies between that
date's sunrise and the next, all read with the date's weekday. That is how
Prokerala's anandadi-yoga lists them, including a nakshatra that runs on into
the following calendar day. Measured on eight births: every yoga id and every
window matches, boundaries within two seconds.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import swisseph as swe

from .ephemeris import SiderealScanner, jd_to_datetime, julian_day

NAKSHATRA_ARC = 360.0 / 27.0
# Abhijit: the last quarter of Uttara Ashadha's fourth pada plus the first
# fifteenth of Shravana, 276 deg 40' to 280 deg 53' 20".
ABHIJIT_START = 276.0 + 40.0 / 60.0
ABHIJIT_END = 280.0 + 53.0 / 60.0 + 20.0 / 3600.0
ABHIJIT_INDEX = 21

SCAN_STEP_DAYS = 1.0 / 24.0
BISECTION_DAYS = 0.05 / 86400.0

# (name, type, description). The nine marked True are Prokerala's own strings,
# copied from their responses; the rest are the classical names awaiting a
# measurement.
YOGAS = [
    ("Ananda", "Siddhi", "Good", False),
    ("Kaal", "Mrutyu", "Bad", True),
    ("Dhumra", "Dukkh", "Bad", True),
    ("Prajapati", "Soubhagya", "Good", True),
    ("Saumya", "Bahu Sukha", "Good", False),
    ("Dhwanksha", "Dhana Kshaya", "Bad", False),
    ("Dhwaja", "Soubhagya", "Good", True),
    ("Sreevatsa", "Sukha", "Good", True),
    ("Vajra", "Kshaya", "Bad", False),
    ("Mudgara", "Lakshmi Kshaya", "Bad", False),
    ("Chatra", "Raja Sanmana", "Good", False),
    ("Mitra", "Pushti", "Good", False),
    ("Manasa", "Soubhagya", "Good", False),
    ("Padma", "Dhanagama", "Good", False),
    ("Lumbaka", "Dhana Kshaya", "Bad", False),
    ("Utpata", "Prana Nasha", "Bad", False),
    ("Mrityu", "Mrutyu", "Bad", False),
    ("Kana", "Klesha", "Bad", False),
    ("Siddhi", "Karya Siddhi", "Good", False),
    ("Shubha", "Kalyana", "Good", False),
    ("Amrita", "Raja Sanmana", "Good", False),
    ("Musala", "Dhana Kshaya", "Bad", False),
    ("Gada", "Kshaya", "Bad", True),
    ("Matanga", "Kul Vruddhi", "Good", True),
    ("Rakshasa", "Maha Kashta", "Bad", True),
    ("Chara", "Karya Siddhi", "Good", True),
    ("Sthira", "Griharambha", "Good", False),
    ("Vardhamana", "Vivaha", "Good", False),
]
assert len(YOGAS) == 28


def star_of(longitude: float) -> int:
    """Index on the 28-star scheme, Abhijit = 21."""
    longitude %= 360.0
    if ABHIJIT_START <= longitude < ABHIJIT_END:
        return ABHIJIT_INDEX
    star = int(longitude / NAKSHATRA_ARC)
    return star if longitude < ABHIJIT_START else star + 1


def yoga_index(star: int, weekday: int) -> int:
    """Weekday 0 = Sunday."""
    return (star - 4 * weekday) % 28


def _windows(scanner: SiderealScanner, start_jd: float,
             end_jd: float) -> list[tuple[float, float, int]]:
    """Spans of constant 28-scheme star between two instants."""
    def star(jd: float) -> int:
        return star_of(scanner.longitude(jd, swe.MOON))

    edges = [start_jd]
    previous, previous_star = start_jd, star(start_jd)
    jd = start_jd + SCAN_STEP_DAYS
    while jd < end_jd:
        current = star(jd)
        if current != previous_star:
            low, high = previous, jd
            while high - low > BISECTION_DAYS:
                middle = (low + high) / 2
                if star(middle) == previous_star:
                    low = middle
                else:
                    high = middle
            edges.append(high)
            previous_star = current
        previous, jd = jd, jd + SCAN_STEP_DAYS
    edges.append(end_jd)
    return [(a, b, star((a + b) / 2)) for a, b in zip(edges, edges[1:])]


def day(sunrise: datetime, next_sunrise: datetime, weekday: int,
        utc_offset_hours: float) -> list[dict]:
    """The anandadi yogas of one sunrise-to-sunrise day, in local time."""
    offset = timedelta(hours=utc_offset_hours)
    begin = julian_day(sunrise - offset)
    finish = julian_day(next_sunrise - offset)
    # A nakshatra lasts at most about a day and a quarter; scan wide enough
    # to see where the first and last ones began and ended.
    spans = _windows(SiderealScanner(), begin - 1.5, finish + 1.5)

    out = []
    for start_jd, end_jd, star in spans:
        if end_jd <= begin or start_jd >= finish:
            continue
        index = yoga_index(star, weekday)
        name, kind, description, measured = YOGAS[index]
        out.append({
            "id": index, "name": name, "type": kind, "description": description,
            "start": (jd_to_datetime(start_jd) + offset).isoformat(),
            "end": (jd_to_datetime(end_jd) + offset).isoformat(),
            "label_parity": "verified" if measured else "unverified",
        })
    return out

