"""Gochara: transits measured against the natal chart.

Sade Sati, Kantaka Shani, Ashtama Shani, and planetary returns. Everything here
is derived by scanning the ephemeris and bisecting to the exact crossing, so
retrograde re-entries are handled naturally rather than approximated.

All dates are returned in the chart's local timezone.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import swisseph as swe

from . import provenance
from .constants import SIGNS, SIGNS_EN, SIGN_LORDS
from .ephemeris import SiderealScanner, jd_to_datetime, julian_day

BODIES = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS, "Mercury": swe.MERCURY,
    "Jupiter": swe.JUPITER, "Venus": swe.VENUS, "Saturn": swe.SATURN,
}

# Coarse scan steps, in days. Chosen so a body cannot cross a whole 30 degree
# sign between samples: Saturn moves at most ~0.13 deg/day, Jupiter ~0.24.
SCAN_STEP = {
    "Saturn": 5.0, "Jupiter": 3.0, "Mars": 1.0,
    "Sun": 1.0, "Venus": 1.0, "Mercury": 1.0, "Moon": 0.1,
}

BISECTION_SECONDS = 1.0

SADE_SATI_PHASES = {
    -1: ("rising", "Saturn in the 12th from natal Moon - losses, expenses, sleep disturbed"),
    0: ("peak", "Saturn over the natal Moon - the heaviest phase, mind and body under load"),
    1: ("setting", "Saturn in the 2nd from natal Moon - family and finances tested, easing"),
}

KANTAKA_HOUSES = (4, 7, 10)
ASHTAMA_HOUSE = 8
DHAIYYA_HOUSE = 4

# Prokerala's own vocabulary, reproduced verbatim so `prokerala_style` is a
# drop-in replacement for their /sade-sati endpoint. Note they flag the 4th and
# 8th as "sade sati" too, which is the Panoti model rather than the strict
# 12th-1st-2nd definition. They do not flag the 7th or 10th at all, so classical
# Kantaka Shani is reported separately under `saturn_afflictions`.
PROKERALA_PHASES = {-1: "Rising", 0: "Peak", 1: "Setting"}
PROKERALA_DHAIYYA = "Small Panoti"
PROKERALA_ASHTAMA = "Ashtama Sani"
PROKERALA_ACTIVE = "You are going through sade sati phase and you are in {phase} phase. "
PROKERALA_INACTIVE = "You are not going through Sade Sati phase now. "

RETURN_PERIODS = {"Jupiter": 11.86, "Saturn": 29.46}


@dataclass(frozen=True)
class Interval:
    sign: int
    start_jd: float
    end_jd: float


def _sign_of(longitude: float) -> int:
    return int(longitude % 360.0 / 30.0)


def _bisect_ingress(
    scanner: SiderealScanner, body: int, low_jd: float, high_jd: float, target_sign: int
) -> float:
    """Narrow down the instant a body enters `target_sign`, to one second."""
    tolerance = BISECTION_SECONDS / 86400.0
    while high_jd - low_jd > tolerance:
        mid = (low_jd + high_jd) / 2.0
        if _sign_of(scanner.longitude(mid, body)) == target_sign:
            high_jd = mid
        else:
            low_jd = mid
    return high_jd


def sign_timeline(
    scanner: SiderealScanner, graha: str, start_jd: float, end_jd: float
) -> list[Interval]:
    """Every contiguous stretch the graha spends in one sign, retrogrades included."""
    body = BODIES[graha]
    step = SCAN_STEP[graha]

    intervals: list[Interval] = []
    jd = start_jd
    current_sign = _sign_of(scanner.longitude(jd, body))
    run_start = jd

    while jd < end_jd:
        nxt = min(jd + step, end_jd)
        sign = _sign_of(scanner.longitude(nxt, body))
        if sign != current_sign:
            boundary = _bisect_ingress(scanner, body, jd, nxt, sign)
            intervals.append(Interval(current_sign, run_start, boundary))
            current_sign = sign
            run_start = boundary
        jd = nxt

    intervals.append(Interval(current_sign, run_start, end_jd))
    return intervals


def _merge_adjacent(intervals: list[Interval]) -> list[Interval]:
    """Collapse retrograde flip-flops back into single stretches per sign."""
    merged: list[Interval] = []
    for interval in intervals:
        if merged and merged[-1].sign == interval.sign:
            merged[-1] = Interval(interval.sign, merged[-1].start_jd, interval.end_jd)
        else:
            merged.append(interval)
    return merged


def _local(jd: float, offset: timedelta) -> str:
    return (jd_to_datetime(jd) + offset).isoformat()


def _sign_block(index: int) -> dict:
    return {
        "index": index,
        "name": SIGNS[index],
        "name_en": SIGNS_EN[index],
        "lord": SIGN_LORDS[index],
    }


def sade_sati(
    scanner: SiderealScanner,
    natal_moon_sign: int,
    birth_jd: float,
    offset: timedelta,
    years_before: float = 5.0,
    years_after: float = 95.0,
) -> dict:
    """Every Sade Sati cycle across the life.

    Sade Sati runs from Saturn's first entry into the 12th from the natal Moon
    until its final exit from the 2nd. Retrograde re-entries are folded into one
    cycle rather than reported as separate ones.
    """
    window = {(natal_moon_sign + d) % 12: d for d in (-1, 0, 1)}

    start_jd = birth_jd - years_before * 365.25
    end_jd = birth_jd + years_after * 365.25
    timeline = _merge_adjacent(sign_timeline(scanner, "Saturn", start_jd, end_jd))

    cycles: list[dict] = []
    current: list[Interval] = []
    for interval in timeline:
        if interval.sign in window:
            current.append(interval)
        elif current:
            cycles.append(_build_cycle(current, window, offset))
            current = []
    if current:
        cycles.append(_build_cycle(current, window, offset))

    return {
        "definition": "Saturn transiting the 12th, 1st and 2nd signs from the natal Moon",
        "natal_moon_sign": _sign_block(natal_moon_sign),
        "cycles": cycles,
    }


def _build_cycle(intervals: list[Interval], window: dict, offset: timedelta) -> dict:
    phases = []
    for interval in intervals:
        name, meaning = SADE_SATI_PHASES[window[interval.sign]]
        phases.append({
            "phase": name,
            "meaning": meaning,
            "sign": _sign_block(interval.sign),
            "start": _local(interval.start_jd, offset),
            "end": _local(interval.end_jd, offset),
            "duration_days": round(interval.end_jd - interval.start_jd, 3),
        })
    start_jd = intervals[0].start_jd
    end_jd = intervals[-1].end_jd
    # A cycle clipped by the scan window is partial, not a real 7.5-year run.
    complete = {window[i.sign] for i in intervals} == {-1, 0, 1}
    return {
        "start": _local(start_jd, offset),
        "end": _local(end_jd, offset),
        "duration_years": round((end_jd - start_jd) / 365.25, 3),
        "complete": complete,
        "phases": phases,
    }


def saturn_afflictions(
    scanner: SiderealScanner,
    natal_moon_sign: int,
    birth_jd: float,
    offset: timedelta,
    years_after: float = 95.0,
) -> dict:
    """Kantaka Shani (4th, 7th, 10th from Moon) and Ashtama Shani (8th)."""
    timeline = _merge_adjacent(
        sign_timeline(scanner, "Saturn", birth_jd, birth_jd + years_after * 365.25)
    )

    def periods(houses: tuple[int, ...]) -> list[dict]:
        wanted = {(natal_moon_sign + h - 1) % 12: h for h in houses}
        return [
            {
                "house_from_moon": wanted[i.sign],
                "sign": _sign_block(i.sign),
                "start": _local(i.start_jd, offset),
                "end": _local(i.end_jd, offset),
            }
            for i in timeline if i.sign in wanted
        ]

    return {
        "dhaiyya": {
            "definition": (
                "Saturn transiting the 4th from the natal Moon - Prokerala calls "
                "this Small Panoti"
            ),
            "periods": periods((DHAIYYA_HOUSE,)),
        },
        "kantaka_shani": {
            "definition": "Saturn transiting the 4th, 7th or 10th from the natal Moon",
            "periods": periods(KANTAKA_HOUSES),
        },
        "ashtama_shani": {
            "definition": "Saturn transiting the 8th from the natal Moon",
            "periods": periods((ASHTAMA_HOUSE,)),
        },
    }


def returns(
    scanner: SiderealScanner,
    graha: str,
    natal_longitude: float,
    birth_jd: float,
    offset: timedelta,
    count: int = 8,
) -> list[dict]:
    """Instants when a graha comes back to its natal longitude.

    Retrograde motion means Jupiter and Saturn can cross their natal degree
    three times around a return; all crossings are reported.
    """
    body = BODIES[graha]
    step = SCAN_STEP[graha]
    horizon = birth_jd + count * RETURN_PERIODS[graha] * 365.25

    def offset_from_natal(jd: float) -> float:
        return (scanner.longitude(jd, body) - natal_longitude + 180.0) % 360.0 - 180.0

    crossings: list[dict] = []
    jd = birth_jd + step
    previous = offset_from_natal(jd)
    while jd < horizon and len(crossings) < count * 3:
        nxt = jd + step
        current = offset_from_natal(nxt)
        # A sign change in the offset means the natal degree was crossed, but
        # ignore the wrap at +/-180 which is the opposition, not the return.
        if previous * current < 0 and abs(previous) < 90.0 and abs(current) < 90.0:
            low, high = jd, nxt
            tolerance = BISECTION_SECONDS / 86400.0
            while high - low > tolerance:
                mid = (low + high) / 2.0
                if offset_from_natal(mid) * previous < 0:
                    high = mid
                else:
                    low = mid
            crossings.append({
                "exact": _local(high, offset),
                "age_years": round((high - birth_jd) / 365.25, 3),
                "retrograde": scanner.speed(high, body) < 0,
            })
        previous = current
        jd = nxt

    return crossings


def build(
    natal: dict,
    birth_local: datetime,
    utc_offset_hours: float,
    ayanamsa: str = "lahiri",
    equinox: str = "mean",
    reference_time: datetime | None = None,
    include_returns: bool = True,
) -> dict:
    """Full gochara block for a natal chart produced by `chart.build()`."""
    scanner = SiderealScanner(ayanamsa=ayanamsa, equinox=equinox)
    offset = timedelta(hours=utc_offset_hours)
    birth_jd = julian_day(birth_local - offset)

    now_local = reference_time or datetime.now()
    now_jd = julian_day(now_local - offset)

    natal_moon_sign = natal["grahas"]["Moon"]["sign_index"]
    lagna_sign = natal["lagna"]["sign_index"]

    current = {}
    for name, body in BODIES.items():
        longitude = scanner.longitude(now_jd, body)
        sign = _sign_of(longitude)
        current[name] = {
            "longitude": round(longitude, 9),
            "sign": _sign_block(sign),
            "degree_in_sign": round(longitude % 30.0, 6),
            "retrograde": scanner.speed(now_jd, body) < 0,
            "house_from_lagna": (sign - lagna_sign) % 12 + 1,
            "house_from_moon": (sign - natal_moon_sign) % 12 + 1,
        }
    rahu = scanner.longitude(now_jd, swe.MEAN_NODE)
    for name, longitude in (("Rahu", rahu), ("Ketu", rahu + 180.0)):
        sign = _sign_of(longitude)
        current[name] = {
            "longitude": round(longitude % 360.0, 9),
            "sign": _sign_block(sign),
            "degree_in_sign": round(longitude % 30.0, 6),
            "retrograde": True,
            "house_from_lagna": (sign - lagna_sign) % 12 + 1,
            "house_from_moon": (sign - natal_moon_sign) % 12 + 1,
        }

    sade = sade_sati(scanner, natal_moon_sign, birth_jd, offset)
    active = next(
        (c for c in sade["cycles"]
         if datetime.fromisoformat(c["start"]) <= now_local < datetime.fromisoformat(c["end"])),
        None,
    )
    if active:
        phase = next(
            (p for p in active["phases"]
             if datetime.fromisoformat(p["start"]) <= now_local < datetime.fromisoformat(p["end"])),
            None,
        )
        sade["currently_active"] = True
        sade["current_cycle"] = {"start": active["start"], "end": active["end"]}
        sade["current_phase"] = phase
    else:
        upcoming = next(
            (c for c in sade["cycles"] if datetime.fromisoformat(c["start"]) > now_local), None
        )
        sade["currently_active"] = False
        sade["current_phase"] = None
        sade["next_cycle"] = (
            {"start": upcoming["start"], "end": upcoming["end"]} if upcoming else None
        )

    saturn_house = current["Saturn"]["house_from_moon"]
    block = {
        "as_of": now_local.isoformat(),
        "reference": "sidereal, same ayanamsa and equinox as the natal chart",
        "positions": current,
        "sade_sati": sade,
        "saturn_afflictions": saturn_afflictions(scanner, natal_moon_sign, birth_jd, offset),
        "prokerala_style": prokerala_style(saturn_house),
    }

    if include_returns:
        block["returns"] = {
            graha.lower(): returns(
                scanner, graha, natal["grahas"][graha]["longitude"], birth_jd, offset
            )
            for graha in ("Jupiter", "Saturn")
        }

    return block


def prokerala_style(saturn_house_from_moon: int) -> dict:
    """Reproduce Prokerala's /sade-sati response exactly.

    Verified against their API for all five outcomes: Rising, Peak, Setting,
    Small Panoti, Ashtama Sani, and the inactive case.
    """
    if saturn_house_from_moon == 12:
        phase = PROKERALA_PHASES[-1]
    elif saturn_house_from_moon == 1:
        phase = PROKERALA_PHASES[0]
    elif saturn_house_from_moon == 2:
        phase = PROKERALA_PHASES[1]
    elif saturn_house_from_moon == DHAIYYA_HOUSE:
        phase = PROKERALA_DHAIYYA
    elif saturn_house_from_moon == ASHTAMA_HOUSE:
        phase = PROKERALA_ASHTAMA
    else:
        phase = None

    return {
        "is_in_sade_sati": phase is not None,
        "transit_phase": phase,
        "description": (
            PROKERALA_ACTIVE.format(phase=phase) if phase else PROKERALA_INACTIVE
        ),
        "strict_sade_sati": saturn_house_from_moon in (12, 1, 2),
        "saturn_house_from_moon": saturn_house_from_moon,
    }
