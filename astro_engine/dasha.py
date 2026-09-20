"""Vimshottari dasha, computed from the Moon's nakshatra position.

Year length is a real convention disagreement between implementations, not a
settled fact:

    365.25    Julian year  - used by Prokerala and most Indian software (default)
    365.2425  Gregorian mean year
    365.2564  sidereal year - closest to the classical "solar year"

Over a 120-year cycle the Julian and Gregorian choices diverge by about
0.9 days, so mahadasha boundaries shift by a day or two depending which you
pick. Verified against Prokerala: the two agree to the second once the same
year length is used. Override with `year_length` if you need to match a
different source.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from .constants import DASHA_SEQUENCE, DASHA_TOTAL_YEARS, NAKSHATRA_LORDS

# Prokerala rounds the nakshatra traversal fraction to 3 decimals before
# deriving the dasha balance. That costs up to ~1.5 days on a 20-year
# mahadasha, so it is off by default - set it only to reproduce their output.
PROKERALA_TRAVERSED_PRECISION = 3

JULIAN_YEAR = 365.25
GREGORIAN_YEAR = 365.2425
SIDEREAL_YEAR = 365.2564

DAYS_PER_YEAR = JULIAN_YEAR
NAKSHATRA_ARC = 360.0 / 27.0

_LORD_YEARS = dict(DASHA_SEQUENCE)
_ORDER = [lord for lord, _ in DASHA_SEQUENCE]


def _rotate_from(lord: str) -> list[str]:
    start = _ORDER.index(lord)
    return _ORDER[start:] + _ORDER[:start]


def balance_at_birth(
    moon_longitude: float,
    traversed_precision: int | None = None,
) -> tuple[str, float]:
    """Returns the birth dasha lord and the unelapsed fraction of its period.

    `traversed_precision` rounds the traversal fraction to that many decimals.
    Leave it None for full precision; pass 3 to reproduce Prokerala.
    """
    moon_longitude %= 360.0
    nak_index = int(moon_longitude / NAKSHATRA_ARC)
    traversed = (moon_longitude - nak_index * NAKSHATRA_ARC) / NAKSHATRA_ARC
    if traversed_precision is not None:
        traversed = round(traversed, traversed_precision)
    return NAKSHATRA_LORDS[nak_index], 1.0 - traversed


def _subdivide(lord: str, start: datetime, span_days: float, depth: int) -> list[dict]:
    """Recursively split a period into its sub-periods (antar, pratyantar, ...)."""
    if depth <= 0:
        return []
    periods = []
    cursor = start
    for sub_lord in _rotate_from(lord):
        sub_days = span_days * _LORD_YEARS[sub_lord] / DASHA_TOTAL_YEARS
        end = cursor + timedelta(days=sub_days)
        periods.append({
            "lord": sub_lord,
            "start": cursor.isoformat(),
            "end": end.isoformat(),
            "duration_days": round(sub_days, 4),
            "sub_periods": _subdivide(sub_lord, cursor, sub_days, depth - 1),
        })
        cursor = end
    return periods


def vimshottari(
    moon_longitude: float,
    birth: datetime,
    horizon_years: float = 120.0,
    depth: int = 2,
    year_length: float = DAYS_PER_YEAR,
    traversed_precision: int | None = None,
) -> dict:
    """Full Vimshottari timeline from birth. depth=1 gives mahadashas only,
    2 adds antardashas, 3 adds pratyantardashas."""
    birth_lord, balance = balance_at_birth(moon_longitude, traversed_precision)

    # The first mahadasha is partial: it began before birth.
    first_span = _LORD_YEARS[birth_lord] * year_length
    cycle_start = birth - timedelta(days=first_span * (1.0 - balance))

    mahadashas = []
    cursor = cycle_start
    horizon = birth + timedelta(days=horizon_years * year_length)
    for lord in _rotate_from(birth_lord):
        span = _LORD_YEARS[lord] * year_length
        end = cursor + timedelta(days=span)
        mahadashas.append({
            "lord": lord,
            "start": cursor.isoformat(),
            "end": end.isoformat(),
            "duration_years": _LORD_YEARS[lord],
            "sub_periods": _subdivide(lord, cursor, span, depth - 1),
        })
        cursor = end
        if cursor > horizon:
            break

    return {
        "system": "Vimshottari",
        "year_length_days": year_length,
        "traversed_precision": traversed_precision,
        "birth_dasha_lord": birth_lord,
        "balance_at_birth_years": round(balance * _LORD_YEARS[birth_lord], 6),
        "cycle_start": cycle_start.isoformat(),
        "mahadashas": mahadashas,
    }


def active_chain(dasha: dict, moment: datetime) -> list[dict]:
    """The nested lords running at a given moment, outermost first."""
    chain = []
    level = dasha["mahadashas"]
    labels = ["mahadasha", "antardasha", "pratyantardasha", "sookshma", "prana"]
    depth = 0
    while level and depth < len(labels):
        match = next(
            (p for p in level
             if datetime.fromisoformat(p["start"]) <= moment < datetime.fromisoformat(p["end"])),
            None,
        )
        if match is None:
            break
        chain.append({
            "level": labels[depth],
            "lord": match["lord"],
            "start": match["start"],
            "end": match["end"],
        })
        level = match.get("sub_periods") or []
        depth += 1
    return chain
