"""Upagrahas: the shadowy sub-planets.

Two families, computed quite differently.

*Sun-derived* -- Dhuma, Vyatipata, Parivesha, Indrachapa and Upaketu are fixed
offsets from the Sun, so they need no location at all.

*Time-derived* -- Kala, Mrityu, Ardha Prahara, Yamaghanta, Gulika and Mandi are
the Lagna rising at a particular moment. Daylight is cut into eight equal
parts and so is the night; each upagraha belongs to one part:

    part = (weekday index of its ruler - effective vara) mod 8

    Kala -> Sun (0), Mrityu -> Mars (2), Ardha Prahara -> Mercury (3),
    Yamaghanta -> Jupiter (4), Gulika and Mandi -> Saturn (6)

The effective vara is the vara itself by day, and the vara four weekdays later
by night -- the classical rule that night lordship begins with the lord of the
fifth weekday. Within its part each upagraha sits at the midpoint, except
Gulika, which sits at the start; Mandi therefore trails Gulika by half a part.

The modulus is the crux. There are eight parts but only seven weekday lords,
so counting the parts mod 7 (which the "portion of Saturn" phrasing invites)
agrees with the real table for some weekdays and is off by one for others.
Mod 8 is what Prokerala does.

None of this was taken from a text. Prokerala's longitudes for six weekday and
day/night combinations were inverted back into the moment the Lagna held them
and expressed as a fraction of the span; all 36 measurements landed on an
exact eighth or half-eighth, and the formula above reproduces every one.

Parity note: those fractions only come out exact against *geometric* sunrise
and sunset (disc centre, no refraction), the convention Prokerala uses
throughout. Two caveats remain, both small:

  * day births agree to within 25 arcsec, the residue of sunrise and sunset
    differing by well under a second;
  * night births agree to within about a arcminute, because the sunrise that
    closes the night is one Prokerala places 4 seconds earlier than both Swiss
    Ephemeris and its own panchang endpoint reports for the same morning.
"""

from __future__ import annotations

from .constants import SIGNS, SIGNS_EN, SIGN_LORDS
from .ephemeris import SiderealSky, to_dms

# Sunday = 0, matching constants.WEEKDAYS.
WEEKDAY_LORDS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]

PARTS_PER_SPAN = 8
# Night lordship begins with the lord of the fifth weekday.
NIGHT_VARA_ADVANCE = 4

# Which part-lord each time-derived upagraha belongs to, and where inside that
# part it is taken (0 = start, 0.5 = midpoint).
PART_RULER = {
    "Kala": "Sun",
    "Mrityu": "Mars",
    "Ardha Prahara": "Mercury",
    "Yamaghanta": "Jupiter",
    "Gulika": "Saturn",
    "Mandi": "Saturn",
}
PART_POINT = {
    "Kala": 0.5, "Mrityu": 0.5, "Ardha Prahara": 0.5,
    "Yamaghanta": 0.5, "Gulika": 0.0, "Mandi": 0.5,
}

# Prokerala's ids, so a response can be compared field for field.
UPAGRAHA_IDS = {
    "Dhuma": 121, "Vyatipata": 122, "Parivesha": 123, "Indrachapa": 124,
    "Upaketu": 125, "Kala": 126, "Mrityu": 127, "Ardha Prahara": 128,
    "Yamaghanta": 129, "Gulika": 130, "Mandi": 131,
}
ORDER = list(UPAGRAHA_IDS)
SUN_DERIVED = ORDER[:5]
TIME_DERIVED = ORDER[5:]

DHUMA_OFFSET = 133.0 + 20.0 / 60.0      # 133 deg 20 min
UPAKETU_OFFSET = 16.0 + 40.0 / 60.0     # 16 deg 40 min


def sun_derived(sun_longitude: float) -> dict[str, float]:
    """The five offsets from the Sun. All follow from Dhuma."""
    dhuma = (sun_longitude + DHUMA_OFFSET) % 360.0
    vyatipata = (360.0 - dhuma) % 360.0
    parivesha = (vyatipata + 180.0) % 360.0
    indrachapa = (360.0 - parivesha) % 360.0
    upaketu = (indrachapa + UPAKETU_OFFSET) % 360.0
    return {
        "Dhuma": dhuma,
        "Vyatipata": vyatipata,
        "Parivesha": parivesha,
        "Indrachapa": indrachapa,
        "Upaketu": upaketu,
    }


def effective_vara(vara_index: int, by_night: bool) -> int:
    if not by_night:
        return vara_index
    return (vara_index + NIGHT_VARA_ADVANCE) % len(WEEKDAY_LORDS)


def part_index(upagraha: str, vara_index: int, by_night: bool) -> int:
    """0-based part number for one upagraha on one vara."""
    ruler = WEEKDAY_LORDS.index(PART_RULER[upagraha])
    return (ruler - effective_vara(vara_index, by_night)) % PARTS_PER_SPAN


def part_bounds(index: int, span_start_jd: float, span_end_jd: float) -> tuple[float, float]:
    width = (span_end_jd - span_start_jd) / PARTS_PER_SPAN
    return span_start_jd + index * width, span_start_jd + (index + 1) * width


def _describe(name: str, longitude: float, lagna_sign: int) -> dict:
    longitude %= 360.0
    sign = int(longitude / 30.0)
    return {
        "id": UPAGRAHA_IDS[name],
        "name": name,
        "longitude": round(longitude, 9),
        "degree_in_sign": round(longitude % 30.0, 9),
        "dms": to_dms(longitude % 30.0),
        "is_retrograde": False,
        "house": (sign - lagna_sign) % 12 + 1,
        "rasi": {"index": sign, "name": SIGNS[sign], "name_en": SIGNS_EN[sign],
                 "lord": SIGN_LORDS[sign]},
    }


def compute(
    jd_ut: float,
    latitude: float,
    longitude: float,
    sun_longitude: float,
    lagna_sign: int,
    solar: dict,
    vara_index: int,
    ayanamsa: str = "lahiri",
    equinox: str = "mean",
    house_system: bytes = b"P",
) -> list[dict]:
    """Every upagraha for one birth, in Prokerala's listing order.

    `solar` is the dict from `ephemeris.sun_rise_set`; `vara_index` is the vara
    the Vedic day opened with, not the calendar weekday.
    """
    values = sun_derived(sun_longitude)

    # sun_rise_set anchors us to the Vedic day containing jd_ut, so the birth is
    # either between that sunrise and its sunset, or in the night that follows.
    by_night = jd_ut >= solar["sunset_jd"]
    span = ((solar["sunset_jd"], solar["next_sunrise_jd"]) if by_night
            else (solar["sunrise_jd"], solar["sunset_jd"]))

    for name in TIME_DERIVED:
        begin, end = part_bounds(part_index(name, vara_index, by_night), *span)
        moment = begin + (end - begin) * PART_POINT[name]
        sky = SiderealSky(moment, ayanamsa=ayanamsa, equinox=equinox)
        values[name] = sky.angles(latitude, longitude, house_system)["ascendant"].longitude

    return [_describe(name, values[name], lagna_sign) for name in ORDER]
