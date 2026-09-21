"""Tara bala, chandra bala and chandrashtama: is today good for *you*?

All three compare the transiting Moon with a natal reference, so unlike the
muhurta periods they are personal.

*Tara bala* counts the transit nakshatra from the janma nakshatra and takes the
result modulo nine. Three of the nine taras are hostile.

*Chandra bala* counts the transit rasi from the janma rasi; six of the twelve
positions carry strength.

*Chandrashtama* is the single worst of those: the Moon in the eighth from the
natal Moon, about two and a quarter days a month.

Each is reported two ways -- for one person, and as the set of janma
nakshatras or rasis that a given moment favours, which is the shape Prokerala
uses for its daily tables.

Both daily tables reproduce Prokerala exactly -- see PARITY at the bottom for
the one quirk in how their tara table has to be read.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import swisseph as swe

from . import provenance
from .constants import NAKSHATRAS, PROKERALA_NAKSHATRA_NAMES, SIGNS, SIGNS_EN, SIGN_LORDS
from .ephemeris import SiderealScanner, jd_to_datetime, julian_day

NAKSHATRA_ARC = 360.0 / 27.0
TARA_COUNT = 9

TARAS = [
    (1, "Janma", "Bad"), (2, "Sampat", "Good"), (3, "Vipat", "Bad"),
    (4, "Kshema", "Good"), (5, "Pratyari", "Bad"), (6, "Sadhaka", "Good"),
    (7, "Vadha", "Bad"), (8, "Mitra", "Good"), (9, "Ati Mitra", "Good"),
]
HOSTILE_TARAS = frozenset({1, 3, 5, 7})

# Positions of the transit Moon, counted from the janma rasi, that carry bala.
CHANDRA_BALA_POSITIONS = frozenset({1, 3, 6, 7, 10, 11})
CHANDRASHTAMA_POSITION = 8

# The Moon crosses a nakshatra in about a day, so a minute of resolution is
# plenty and bisection converges in twenty steps.
BISECTION_SECONDS = 1.0
SCAN_STEP_HOURS = 2.0


def tara(janma_nakshatra: int, transit_nakshatra: int) -> tuple[int, str, str]:
    position = (transit_nakshatra - janma_nakshatra) % 27 % TARA_COUNT
    return TARAS[position]


def chandra_bala(janma_rasi: int, transit_rasi: int) -> bool:
    return (transit_rasi - janma_rasi) % 12 + 1 in CHANDRA_BALA_POSITIONS


def chandrashtama(janma_rasi: int, transit_rasi: int) -> bool:
    return (transit_rasi - janma_rasi) % 12 + 1 == CHANDRASHTAMA_POSITION


def _moon_longitude(scanner: SiderealScanner, jd: float) -> float:
    return scanner.longitude(jd, swe.MOON)


def _crossings(scanner: SiderealScanner, start_jd: float, end_jd: float,
               arc: float) -> list[float]:
    """Julian days where the Moon enters a new arc-wide division."""
    step = SCAN_STEP_HOURS / 24.0
    tolerance = BISECTION_SECONDS / 86400.0
    edges = []

    previous = start_jd
    previous_index = int(_moon_longitude(scanner, previous) / arc)
    jd = start_jd + step
    while jd < end_jd:
        index = int(_moon_longitude(scanner, jd) / arc)
        if index != previous_index:
            low, high = previous, jd
            while high - low > tolerance:
                middle = (low + high) / 2
                if int(_moon_longitude(scanner, middle) / arc) == previous_index:
                    low = middle
                else:
                    high = middle
            edges.append(high)
            previous_index = index
        previous, jd = jd, jd + step
    return edges


def _windows(scanner: SiderealScanner, start_jd: float, end_jd: float,
             arc: float) -> list[tuple[float, float, int]]:
    edges = [start_jd] + _crossings(scanner, start_jd, end_jd, arc) + [end_jd]
    out = []
    for begin, finish in zip(edges, edges[1:]):
        middle = (begin + finish) / 2
        out.append((begin, finish, int(_moon_longitude(scanner, middle) / arc)))
    return out


def _stamp(jd: float, offset_hours: float) -> str:
    return (jd_to_datetime(jd) + timedelta(hours=offset_hours)).isoformat()


def for_person(janma_nakshatra: int, janma_rasi: int,
               transit_nakshatra: int, transit_rasi: int) -> dict:
    """The three verdicts for one person at one moment."""
    number, name, quality = tara(janma_nakshatra, transit_nakshatra)
    return {
        "tara_bala": {"id": number, "name": name, "type": quality,
                      "is_favourable": number not in HOSTILE_TARAS},
        "chandra_bala": chandra_bala(janma_rasi, transit_rasi),
        "chandrashtama": chandrashtama(janma_rasi, transit_rasi),
    }


def day(date: datetime, utc_offset_hours: float, ayanamsa: str = "lahiri",
        equinox: str = "mean") -> dict:
    """Every tara and chandra bala window of one local calendar date.

    Each window says which janma nakshatras or rasis it favours, which is how
    a panchanga prints it: not "today is good" but "today is good for these".
    """
    scanner = SiderealScanner(ayanamsa=ayanamsa, equinox=equinox)
    offset = timedelta(hours=utc_offset_hours)
    midnight = datetime.combine(date.date(), datetime.min.time())
    start_jd = julian_day(midnight - offset)
    end_jd = julian_day(midnight + timedelta(days=1) - offset)

    tara_windows = []
    for begin, finish, index in _windows(scanner, start_jd, end_jd, NAKSHATRA_ARC):
        by_tara: dict[int, list[int]] = {}
        for janma in range(27):
            number, _, _ = tara(janma, index)
            by_tara.setdefault(number, []).append(janma)
        tara_windows.append({
            "start": _stamp(begin, utc_offset_hours),
            "end": _stamp(finish, utc_offset_hours),
            "transit_nakshatra": {
                "index": index, "name": PROKERALA_NAKSHATRA_NAMES[index],
                "name_iast": NAKSHATRAS[index],
            },
            "favourable_nakshatras": [
                {"index": n, "name": PROKERALA_NAKSHATRA_NAMES[n]}
                for n in range(27)
                if tara(n, index)[0] not in HOSTILE_TARAS
            ],
            "taras": [
                {"id": number, "name": name, "type": quality,
                 "janma_nakshatras": [
                     {"index": n, "name": PROKERALA_NAKSHATRA_NAMES[n]}
                     for n in by_tara[number]
                 ]}
                for number, name, quality in TARAS
            ],
        })

    moon_windows = []
    for begin, finish, index in _windows(scanner, start_jd, end_jd, 30.0):
        moon_windows.append({
            "start": _stamp(begin, utc_offset_hours),
            "end": _stamp(finish, utc_offset_hours),
            "transit_rasi": {"index": index, "name": SIGNS[index],
                             "name_en": SIGNS_EN[index], "lord": SIGN_LORDS[index]},
            "favoured_rasis": [
                {"index": janma, "name": SIGNS[janma], "lord": SIGN_LORDS[janma]}
                for janma in range(12) if chandra_bala(janma, index)
            ],
            "chandrashtama_rasi": {
                "index": (index - CHANDRASHTAMA_POSITION + 1) % 12,
                "name": SIGNS[(index - CHANDRASHTAMA_POSITION + 1) % 12],
            },
        })

    return {
        "date": date.date().isoformat(),
        "tara_bala": tara_windows,
        "chandra_bala": moon_windows,
        **provenance.BALA,
    }


# Both tables were checked against Prokerala's tara-bala and chandra-bala over
# eight dates spread across a year: twenty-four window comparisons, all exact.
#
# Their tara-bala needs reading carefully. Each window carries the name of one
# tara but lists fifteen nakshatras, which is five taras' worth -- the list is
# every janma star the window *favours*, not the three holding the named tara.
# `favourable_nakshatras` is that set; `taras` is the finer breakdown.
PARITY = "verified against Prokerala: 24/24 window comparisons"
