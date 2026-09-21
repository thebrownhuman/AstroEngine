"""Krishnamurti Paddhati: cusps, sub lords and significators.

KP departs from classical Jyotisha in three ways, all of them reproduced here:

  * houses are Placidus cusps, not whole signs, and a "house" is the arc from
    its own cusp to the next one rather than a sign;
  * every point carries three lords, not one -- the sign lord, the nakshatra
    (star) lord, and the sub lord, which comes from dividing the nakshatra in
    Vimshottari proportion. Dividing each sub the same way again gives the
    sub-sub lord;
  * a house is judged by its *significators* rather than its occupants: the
    planets sitting in it, the planets in the nakshatras of those planets, the
    lord of the cusp, and the planets in that lord's nakshatra.

The sub lord is the whole point of the system. Because the nine Vimshottari
spans are unequal, a sub can be as short as 0 deg 13' (Sun inside Ketu's star)
or as long as 2 deg 13' (Venus inside Venus's), so the sub lord changes far
faster than the star lord and is what makes KP claim minute-level resolution.

KP normally runs on its own ayanamsa; pass ayanamsa="krishnamurti".
"""

from __future__ import annotations

from . import provenance
from .constants import (
    DASHA_SEQUENCE, DASHA_TOTAL_YEARS, NAKSHATRAS, NAKSHATRA_LORDS,
    PROKERALA_NAKSHATRA_NAMES, SIGNS, SIGNS_EN, SIGN_LORDS,
)

NAKSHATRA_ARC = 360.0 / 27.0
PADA_ARC = NAKSHATRA_ARC / 4.0

# Fraction of a nakshatra each lord's sub occupies, in Vimshottari order.
SUB_FRACTIONS = [(lord, years / DASHA_TOTAL_YEARS) for lord, years in DASHA_SEQUENCE]

BODIES = ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
          "Rahu", "Ketu")
PLANET_IDS = {"Sun": 0, "Moon": 1, "Mercury": 2, "Venus": 3, "Mars": 4,
              "Jupiter": 5, "Saturn": 6, "Rahu": 101, "Ketu": 102}
VEDIC_NAMES = {"Sun": "Ravi", "Moon": "Chandra", "Mercury": "Budha",
               "Venus": "Shukra", "Mars": "Kuja", "Jupiter": "Guru",
               "Saturn": "Shani", "Rahu": "Rahu", "Ketu": "Ketu"}
HOUSE_NAMES = ["Tanu", "Dhan", "Sahaj", "Bandhu", "Putra", "Ari",
               "Yuvati", "Randhra", "Dharma", "Karma", "Labha", "Vyaya"]


def _sequence_from(lord: str) -> list[tuple[str, float]]:
    """Vimshottari order rotated to start at a given lord."""
    start = next(i for i, (name, _) in enumerate(SUB_FRACTIONS) if name == lord)
    return SUB_FRACTIONS[start:] + SUB_FRACTIONS[:start]


def _divide(span_start: float, span_length: float, first_lord: str,
            offset: float) -> tuple[str, float, float]:
    """Vimshottari subdivision of one span.

    Returns the lord holding the offset, and that sub-span's start and width.
    """
    position = span_start
    for lord, fraction in _sequence_from(first_lord):
        width = span_length * fraction
        if position <= offset < position + width:
            return lord, position, width
        position += width
    # Floating point can leave us a hair past the end of the last sub.
    lord, fraction = _sequence_from(first_lord)[-1]
    width = span_length * fraction
    return lord, span_start + span_length - width, width


def lords_of(longitude: float) -> dict:
    """Sign, star, sub and sub-sub lord of a sidereal longitude."""
    longitude %= 360.0
    nakshatra = int(longitude / NAKSHATRA_ARC)
    star_lord = NAKSHATRA_LORDS[nakshatra]
    nakshatra_start = nakshatra * NAKSHATRA_ARC

    sub_lord, sub_start, sub_width = _divide(
        nakshatra_start, NAKSHATRA_ARC, star_lord, longitude
    )
    sub_sub_lord, _, _ = _divide(sub_start, sub_width, sub_lord, longitude)

    sign = int(longitude / 30.0)
    return {
        "longitude": round(longitude, 9),
        "degree": round(longitude % 30.0, 9),
        "rasi": {"index": sign, "name": SIGNS[sign], "name_en": SIGNS_EN[sign],
                 "lord": SIGN_LORDS[sign]},
        "nakshatra": {"index": nakshatra,
                      "name": PROKERALA_NAKSHATRA_NAMES[nakshatra],
                      "name_iast": NAKSHATRAS[nakshatra],
                      "lord": star_lord,
                      "pada": int((longitude - nakshatra_start) / PADA_ARC) + 1},
        "nakshatra_lord": star_lord,
        "sub_lord": sub_lord,
        "sub_sub_lord": sub_sub_lord,
    }


def house_of(longitude: float, cusps: list[float]) -> int:
    """Which KP house a longitude falls in. A house runs cusp to next cusp."""
    longitude %= 360.0
    for index in range(12):
        start = cusps[index] % 360.0
        width = (cusps[(index + 1) % 12] - cusps[index]) % 360.0
        if (longitude - start) % 360.0 < width:
            return index + 1
    return 12


def _body(name: str) -> dict:
    return {"id": PLANET_IDS[name], "name": name, "vedic_name": VEDIC_NAMES[name]}


def houses(cusps: list[float]) -> list[dict]:
    """The twelve cusps with their full KP lordship."""
    out = []
    for index in range(12):
        start = cusps[index] % 360.0
        end = cusps[(index + 1) % 12] % 360.0
        block = lords_of(start)
        out.append({
            "house": {"id": index, "name": HOUSE_NAMES[index], "number": index + 1},
            "start_cusp": {"longitude": round(start, 9), "degree": round(start % 30, 9),
                           "rasi": block["rasi"]},
            "end_cusp": {"longitude": round(end, 9), "degree": round(end % 30, 9),
                         "rasi": lords_of(end)["rasi"]},
            "rasi": block["rasi"],
            "nakshatra": block["nakshatra"],
            "nakshatra_lord": block["nakshatra_lord"],
            "sub_lord": block["sub_lord"],
            "sub_sub_lord": block["sub_sub_lord"],
        })
    return out


def planets(longitudes: dict[str, float], cusps: list[float]) -> list[dict]:
    out = []
    for name in BODIES:
        block = lords_of(longitudes[name])
        out.append({"planet": _body(name), "house": house_of(longitudes[name], cusps),
                    **block})
    return out


def significators(longitudes: dict[str, float], cusps: list[float]) -> list[dict]:
    """The four levels of significator KP reads for each house.

    A planet signifies a house when it sits in it, when it sits in the
    nakshatra of a planet that sits in it, when it owns the cusp, or when it
    sits in the nakshatra of the planet that owns the cusp.
    """
    star_lord = {name: NAKSHATRA_LORDS[int(longitudes[name] % 360.0 / NAKSHATRA_ARC)]
                 for name in BODIES}
    occupants: dict[int, list[str]] = {h: [] for h in range(1, 13)}
    for name in BODIES:
        occupants[house_of(longitudes[name], cusps)].append(name)

    out = []
    for index in range(12):
        number = index + 1
        owner = SIGN_LORDS[int(cusps[index] % 360.0 / 30.0)]
        in_house = occupants[number]
        out.append({
            "house": {"id": index, "name": HOUSE_NAMES[index], "number": number},
            "cusp_occupants": [_body(n) for n in in_house],
            "cusp_nakshatra_occupants": [
                _body(n) for n in BODIES if star_lord[n] in in_house
            ],
            "cusp_owner": _body(owner),
            "cusp_owner_nakshatra_planets": [
                _body(n) for n in BODIES if star_lord[n] == owner
            ],
        })
    return out


def compute(chart: dict, cusps: list[float]) -> dict:
    """Everything KP, from a built chart and its Placidus cusps."""
    longitudes = {name: chart["grahas"][name]["longitude"] for name in BODIES}
    return {
        "houses": houses(cusps),
        "planets": planets(longitudes, cusps),
        "house_significators": significators(longitudes, cusps),
        **provenance.KP,
    }
