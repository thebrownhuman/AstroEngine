"""Auspicious yogas: weekday, nakshatra and tithi combinations.

Six of them, as Prokerala's auspicious-yoga lists them:

  Amrit Siddhi      one nakshatra per weekday
  Sarvartha Siddhi  a set of nakshatras per weekday
  Guru Pushya       Thursday with Pushya
  Ravi Pushya       Sunday with Pushya
  Dwipushkar        Sunday, Tuesday or Saturday, a bhadra tithi (2, 7, 12),
                    and a nakshatra with two padas in each of two signs
  Tripushkar        the same weekdays and tithis, and a nakshatra spread
                    over three signs

The weekday is the Vedic one, sunrise to sunrise. The search covers the
date's sunrise up to the end of the last nakshatra that begins before the
next sunrise. So a Monday combination that begins at Monday's sunrise, inside
a nakshatra that started on Sunday, is reported for the Sunday; one in the
nakshatra after it is not, and nothing before Sunday's sunrise is. Measured
on seven dates.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import swisseph as swe

from .constants import PROKERALA_NAKSHATRA_NAMES
from .ephemeris import SiderealScanner, jd_to_datetime, julian_day

NAKSHATRA_ARC = 360.0 / 27.0
TITHI_ARC = 12.0
SCAN_STEP_DAYS = 1.0 / 48.0
BISECTION_DAYS = 0.05 / 86400.0
WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
TITHI_NAMES = ["Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami", "Shashthi",
               "Saptami", "Ashtami", "Navami", "Dashami", "Ekadashi", "Dwadashi",
               "Trayodashi", "Chaturdashi"]

# Nakshatra indices, 0 = Ashwini.
ASHWINI, KRITTIKA, ROHINI, MRIGASHIRA, PUNARVASU, PUSHYA, ASHLESHA = 0, 2, 3, 4, 6, 7, 8
U_PHALGUNI, HASTA, CHITRA, SWATI, VISHAKHA, ANURADHA, MULA = 11, 12, 13, 14, 15, 16, 18
U_ASHADHA, SHRAVANA, DHANISHTA, P_BHADRAPADA, U_BHADRAPADA, REVATI = 20, 21, 22, 24, 25, 26

AMRIT_SIDDHI = {0: {HASTA}, 1: {MRIGASHIRA}, 2: {ASHWINI}, 3: {ANURADHA},
                4: {PUSHYA}, 5: {REVATI}, 6: {ROHINI}}
SARVARTHA_SIDDHI = {
    0: {HASTA, MULA, U_ASHADHA, U_PHALGUNI, U_BHADRAPADA, PUSHYA, ASHWINI},
    1: {SHRAVANA, ROHINI, MRIGASHIRA, PUSHYA, ANURADHA},
    2: {ASHWINI, U_BHADRAPADA, KRITTIKA, ASHLESHA},
    3: {ROHINI, ANURADHA, HASTA, KRITTIKA, MRIGASHIRA},
    4: {REVATI, ANURADHA, ASHWINI, PUNARVASU, PUSHYA},
    5: {REVATI, ANURADHA, ASHWINI, PUNARVASU, SHRAVANA},
    6: {SHRAVANA, ROHINI, SWATI},
}
PUSHKAR_WEEKDAYS = {0, 2, 6}
BHADRA_TITHIS = {1, 6, 11}            # 0-based within the paksha: 2nd, 7th, 12th
DWIPADA = {MRIGASHIRA, CHITRA, DHANISHTA}
TRIPADA = {KRITTIKA, PUNARVASU, U_PHALGUNI, VISHAKHA, U_ASHADHA, P_BHADRAPADA}


def _spans(value, start_jd: float, end_jd: float) -> list[tuple[float, float, int]]:
    edges = [start_jd]
    previous, previous_value = start_jd, value(start_jd)
    jd = start_jd + SCAN_STEP_DAYS
    while jd < end_jd:
        current = value(jd)
        if current != previous_value:
            low, high = previous, jd
            while high - low > BISECTION_DAYS:
                middle = (low + high) / 2
                if value(middle) == previous_value:
                    low = middle
                else:
                    high = middle
            edges.append(high)
            previous_value = current
        previous, jd = jd, jd + SCAN_STEP_DAYS
    edges.append(end_jd)
    return [(a, b, value((a + b) / 2)) for a, b in zip(edges, edges[1:])]


def _weekday_spans(sunrises: list[float], offset: timedelta) -> list[tuple[float, float, int]]:
    out = []
    for a, b in zip(sunrises, sunrises[1:]):
        local_weekday = ((jd_to_datetime(a) + offset).weekday() + 1) % 7
        out.append((a, b, local_weekday))
    return out


def _intersect(*layers):
    """Overlay span lists; yield (start, end, values...) for each overlap."""
    edges = sorted({e for layer in layers for s in layer for e in s[:2]})
    for a, b in zip(edges, edges[1:]):
        middle = (a + b) / 2
        values = []
        for layer in layers:
            hit = next((v for s, e, v in layer if s <= middle < e), None)
            values.append(hit)
        if None not in values:
            yield a, b, values


def compute(sunrises_utc: list[datetime], utc_offset_hours: float) -> list[dict]:
    """The six yogas and their periods for one date.

    `sunrises_utc` holds four consecutive sunrises: the day before, the date
    itself, the next day and the one after, so that weekdays are known for
    the whole of any nakshatra overlapping the date.
    """
    scanner = SiderealScanner()
    offset = timedelta(hours=utc_offset_hours)
    day_start = julian_day(sunrises_utc[1])
    day_end = julian_day(sunrises_utc[2])

    def nakshatra(jd: float) -> int:
        return int(scanner.longitude(jd, swe.MOON) / NAKSHATRA_ARC)

    def tithi(jd: float) -> int:
        elongation = (scanner.longitude(jd, swe.MOON) - scanner.longitude(jd, swe.SUN)) % 360
        return int(elongation / TITHI_ARC)

    stars = [span for span in _spans(nakshatra, day_start - 1.5, day_end + 1.5)
             if span[1] > day_start and span[0] < day_end]
    begin, finish = day_start, stars[-1][1]
    layers = (
        _weekday_spans([julian_day(t) for t in sunrises_utc], offset),
        stars,
        _spans(tithi, begin - 1.0, finish + 1.0),
    )

    def stamp(jd: float) -> str:
        return (jd_to_datetime(jd) + offset).replace(microsecond=0).isoformat()

    found: dict[str, list[dict]] = {name: [] for name in NAMES}
    for a, b, (weekday, star, lunar_day) in _intersect(*layers):
        if b <= begin or a >= finish:
            continue
        paksha_day = lunar_day % 15
        combos = []
        if star in AMRIT_SIDDHI[weekday]:
            combos.append(("Amrit Siddhi", ["nakshatra", "day"]))
        if star in SARVARTHA_SIDDHI[weekday]:
            combos.append(("Sarvartha Siddhi", ["nakshatra", "day"]))
        if star == PUSHYA and weekday == 4:
            combos.append(("Guru Pushya", ["nakshatra", "day"]))
        if star == PUSHYA and weekday == 0:
            combos.append(("Ravi Pushya", ["nakshatra", "day"]))
        if weekday in PUSHKAR_WEEKDAYS and paksha_day in BHADRA_TITHIS:
            if star in DWIPADA:
                combos.append(("Dwipushkar", ["nakshatra", "tithi", "day"]))
            if star in TRIPADA:
                combos.append(("Tripushkar", ["nakshatra", "tithi", "day"]))
        labels = {"nakshatra": PROKERALA_NAKSHATRA_NAMES[star],
                  "tithi": TITHI_NAMES[paksha_day] if paksha_day < 14 else
                  ("Purnima" if lunar_day == 14 else "Amavasya"),
                  "day": WEEKDAYS[weekday]}
        for name, parts in combos:
            periods = found[name]
            start, end = max(a, begin), min(b, finish)
            if periods and periods[-1]["_end"] == a:
                periods[-1]["_end"] = end
                continue
            periods.append({"_start": start, "_end": end, "combination": [
                {"type": part, "name": labels[part]} for part in parts]})

    out = []
    for index, name in enumerate(NAMES):
        out.append({"id": index, "name": name, "period": [
            {"start": stamp(p["_start"]), "end": stamp(p["_end"]),
             "combination": p["combination"]} for p in found[name]]})
    return out


NAMES = ["Amrit Siddhi", "Sarvartha Siddhi", "Guru Pushya", "Ravi Pushya",
         "Dwipushkar", "Tripushkar"]
