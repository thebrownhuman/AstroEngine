"""Assembles one complete, deterministic birth chart.

The output of `build()` is the only thing an LLM should ever see. The model
interprets these numbers; it never computes them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import ashtakavarga as av
from . import provenance
from . import calendar_points as calendar
from . import doshas as dosha_rules
from . import panchanga, relationships as maitri, transits as gochara
from . import upagraha as upagrahas
from .constants import (
    NATURAL_BENEFICS, NATURAL_MALEFICS, SIGNS, SIGNS_EN, SIGN_LORDS,
    nakshatra_attributes,
)
from .dasha import DAYS_PER_YEAR, active_chain, vimshottari
from .ephemeris import (
    EPHEMERIS_BACKEND, SiderealSky, dignity, jd_to_datetime, julian_day,
    sun_rise_set,
)
from .geo import to_utc
from .vargas import VARGAS

ENGINE_VERSION = "1.1.0"

# Classical graha drishti from BPHS Chapter 26, expressed as house counts from
# the occupied house. BPHS gives special aspects only to Mars, Jupiter and
# Saturn; Rahu and Ketu retain the ordinary seventh aspect here.
SPECIAL_ASPECTS = {
    "Mars": (4, 7, 8),
    "Jupiter": (5, 7, 9),
    "Saturn": (3, 7, 10),
}
DEFAULT_ASPECTS = (7,)


def _local_reference_time(reference_time: datetime | None, timezone: str) -> datetime:
    """Return the dasha/transit reference instant as a local naive datetime.

    Birth-time and dasha periods are represented in the birth location's local
    clock.  An API caller may nevertheless provide an ISO-8601 offset; convert
    that instant into the resolved location timezone before comparing it.
    """
    if reference_time is None:
        return datetime.now()
    if reference_time.tzinfo is None:
        return reference_time
    try:
        return reference_time.astimezone(ZoneInfo(timezone)).replace(tzinfo=None)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"unknown IANA timezone {timezone!r}") from exc

# Jaimini/BPHS rashi drishti. Movable signs aspect fixed signs except the
# adjacent fixed sign; fixed signs aspect movable signs except the adjacent
# movable sign; dual signs aspect the other dual signs.
MOVABLE_SIGNS = frozenset({0, 3, 6, 9})
FIXED_SIGNS = frozenset({1, 4, 7, 10})
DUAL_SIGNS = frozenset({2, 5, 8, 11})

HOUSE_MEANINGS = [
    "self, body, vitality", "wealth, speech, family", "courage, siblings, effort",
    "home, mother, comfort", "intellect, children, purva punya", "debt, disease, enemies",
    "partnership, marriage", "longevity, upheaval, the occult", "dharma, fortune, father",
    "career, status, action", "gains, networks, elder siblings", "loss, expense, moksha",
]


@dataclass(frozen=True)
class BirthData:
    year: int
    month: int
    day: int
    hour: int
    minute: int
    second: int
    latitude: float
    longitude: float
    timezone: str | None = None
    ayanamsa: str = "lahiri"
    node_type: str = "mean"
    house_system: str = "P"
    dasha_year_length: float = DAYS_PER_YEAR
    equinox: str = "mean"
    dasha_traversed_precision: int | None = None
    sunrise_convention: str = "apparent"

    def local_datetime(self) -> datetime:
        return datetime(self.year, self.month, self.day, self.hour, self.minute, self.second)


def _house_of(sign_index: int, lagna_sign: int) -> int:
    return (sign_index - lagna_sign) % 12 + 1


def _sign_block(index: int) -> dict:
    return {
        "index": index,
        "name": SIGNS[index],
        "name_en": SIGNS_EN[index],
        "lord": SIGN_LORDS[index],
    }


def _aspects(positions: dict, lagna_sign: int) -> list[dict]:
    """BPHS planetary/graha drishti: houses and planets each graha aspects."""
    house_occupants: dict[int, list[str]] = {h: [] for h in range(1, 13)}
    for name, pos in positions.items():
        house_occupants[_house_of(pos.sign_index, lagna_sign)].append(name)

    out = []
    for name, pos in positions.items():
        from_house = _house_of(pos.sign_index, lagna_sign)
        counts = SPECIAL_ASPECTS.get(name, DEFAULT_ASPECTS)
        aspected = [(from_house - 1 + (c - 1)) % 12 + 1 for c in counts]
        out.append({
            "graha": name,
            "from_house": from_house,
            "aspects_houses": aspected,
            "aspects_grahas": sorted(
                g for h in aspected for g in house_occupants[h] if g != name
            ),
        })
    return out


def _rashi_aspected_signs(sign: int) -> list[int]:
    if sign in MOVABLE_SIGNS:
        candidates = FIXED_SIGNS
        excluded_difference = 1  # next sign is the adjacent fixed sign
    elif sign in FIXED_SIGNS:
        candidates = MOVABLE_SIGNS
        excluded_difference = 11  # previous sign is the adjacent movable sign
    else:
        candidates = DUAL_SIGNS - {sign}
        excluded_difference = None
    return sorted(
        target for target in candidates
        if excluded_difference is None
        or (target - sign) % 12 != excluded_difference
    )


def _rashi_aspects(positions: dict, lagna_sign: int) -> list[dict]:
    """BPHS/Jaimini sign aspects, kept separate from graha drishti."""
    grahas_by_sign: dict[int, list[str]] = {sign: [] for sign in range(12)}
    for name, pos in positions.items():
        grahas_by_sign[pos.sign_index].append(name)

    out = []
    for name, pos in positions.items():
        signs = _rashi_aspected_signs(pos.sign_index)
        houses = [
            _house_of(sign, lagna_sign)
            for sign in signs
        ]
        out.append({
            "graha": name,
            "from_sign": _sign_block(pos.sign_index),
            "from_house": _house_of(pos.sign_index, lagna_sign),
            "aspects_signs": [_sign_block(sign) for sign in signs],
            "aspects_houses": houses,
            "aspects_grahas": sorted(
                graha for sign in signs for graha in grahas_by_sign[sign]
            ),
        })
    return out


def _graha_aspect_targets(source: str, source_sign: int) -> set[int]:
    counts = SPECIAL_ASPECTS.get(source, DEFAULT_ASPECTS)
    return {(source_sign + count - 1) % 12 for count in counts}


def _bphs_nature(
    positions: dict, name: str, sun_longitude: float,
) -> tuple[str, list[str]]:
    """Contextual benefic/malefic result from BPHS Chapter 3, shloka 11."""
    natural = (
        "benefic" if name in NATURAL_BENEFICS
        else "malefic" if name in NATURAL_MALEFICS
        else "neutral"
    )
    if name not in ("Moon", "Mercury"):
        return natural, ["natural classification"]

    moon_sun_distance = (positions["Moon"].longitude - sun_longitude) % 360.0
    # 0° is Amavasya (dark Moon); 180° is Purnima (full Moon, bright half).
    waning_moon = moon_sun_distance > 180.0 or moon_sun_distance < 1e-9
    moon_mercury_together = (
        positions["Moon"].sign_index == positions["Mercury"].sign_index
    )
    if moon_mercury_together and waning_moon:
        return "benefic", ["waning Moon and Mercury are joined; BPHS exception"]

    if name == "Mercury":
        joined_malefics = sorted(
            other for other in NATURAL_MALEFICS
            if other in positions
            and positions[other].sign_index == positions["Mercury"].sign_index
        )
        if joined_malefics:
            return "malefic", [f"joined with natural malefic(s): {joined_malefics}"]
        return "benefic", ["Mercury is not joined with a natural malefic"]

    if not waning_moon:
        return "benefic", ["waxing Moon"]

    benefic_sources = []
    for source in ("Mercury", "Jupiter", "Venus"):
        source_nature, _ = _bphs_nature(positions, source, sun_longitude)
        if source_nature != "benefic":
            continue
        source_sign = positions[source].sign_index
        if (
            source_sign == positions["Moon"].sign_index
            or positions["Moon"].sign_index in _graha_aspect_targets(source, source_sign)
        ):
            benefic_sources.append(source)
    if benefic_sources:
        return "benefic", [f"waning Moon joined/aspected by benefic(s): {benefic_sources}"]
    return "malefic", ["waning Moon"]


def _varga_table(positions: dict, lagna_longitude: float, which: list[str]) -> dict:
    table = {}
    for key in which:
        if key not in VARGAS:
            raise ValueError(f"unknown varga {key!r}; expected one of {sorted(VARGAS)}")
        label, fn = VARGAS[key]
        varga_lagna = fn(lagna_longitude)
        bodies = {}
        for name, pos in positions.items():
            sign = fn(pos.longitude)
            bodies[name] = {
                "sign": _sign_block(sign),
                "house": (sign - varga_lagna) % 12 + 1,
            }
        table[key] = {
            "name": label,
            "lagna": _sign_block(varga_lagna),
            "grahas": bodies,
        }
    return table


def build(
    birth: BirthData,
    vargas: list[str] | None = None,
    dasha_depth: int = 2,
    reference_time: datetime | None = None,
    include_transits: bool = False,
    include_ashtakavarga: bool = False,
    include_upagrahas: bool = False,
    include_relationships: bool = False,
    include_doshas: bool = False,
    include_calendar: bool = False,
    include_nakshatra_info: bool = False,
) -> dict:
    local = birth.local_datetime()
    utc, tz_info = to_utc(local, birth.latitude, birth.longitude, birth.timezone)
    jd = julian_day(utc)

    sky = SiderealSky(
        jd,
        ayanamsa=birth.ayanamsa,
        node_type=birth.node_type,
        equinox=birth.equinox,
    )
    positions = sky.positions()
    sun_longitude = positions["Sun"].longitude

    offset = timedelta(hours=tz_info["utc_offset_hours"])
    # Validate the solar day before asking Swiss Ephemeris for house cusps.
    # At circumpolar latitudes houses_ex can fail before rise_trans reports the
    # missing sunrise/sunset; the API should expose the useful 422 either way.
    solar = sun_rise_set(
        jd, birth.latitude, birth.longitude, convention=birth.sunrise_convention
    )
    angles = sky.angles(birth.latitude, birth.longitude, birth.house_system.encode())
    lagna = angles["ascendant"]
    lagna_sign = lagna.sign_index

    vedic_day_start_local = jd_to_datetime(solar["sunrise_jd"]) + offset
    # Python's weekday() is Monday=0; the vara list is Sunday=0.
    vara_index = (vedic_day_start_local.weekday() + 1) % 7
    civil_vara_index = (local.weekday() + 1) % 7

    grahas = {}
    for name, pos in positions.items():
        entry = pos.as_dict()
        entry["house"] = _house_of(pos.sign_index, lagna_sign)
        entry["dignity"] = dignity(name, pos, sun_longitude)
        natural_nature = (
            "benefic" if name in NATURAL_BENEFICS
            else "malefic" if name in NATURAL_MALEFICS
            else "neutral"
        )
        bphs_nature, bphs_reasons = _bphs_nature(positions, name, sun_longitude)
        entry["nature"] = bphs_nature
        entry["natural_nature"] = natural_nature
        entry["bphs_nature"] = bphs_nature
        entry["bphs_nature_reasons"] = bphs_reasons
        grahas[name] = entry

    houses = []
    for h in range(1, 13):
        sign = (lagna_sign + h - 1) % 12
        houses.append({
            "house": h,
            "sign": _sign_block(sign),
            "lord": SIGN_LORDS[sign],
            "significations": HOUSE_MEANINGS[h - 1],
            "occupants": [n for n, g in grahas.items() if g["house"] == h],
        })

    dasha = vimshottari(
        positions["Moon"].longitude, local, depth=dasha_depth,
        year_length=birth.dasha_year_length,
        traversed_precision=birth.dasha_traversed_precision,
    )
    now = _local_reference_time(reference_time, tz_info["timezone"])

    chart = {
        "engine": {
            "name": "astro_engine",
            "version": ENGINE_VERSION,
            "ephemeris": EPHEMERIS_BACKEND,
            "zodiac": "sidereal",
            "ayanamsa": birth.ayanamsa,
            "ayanamsa_degrees": round(sky.ayanamsa_value(), 8),
            "house_convention": "whole_sign",
            "node_type": birth.node_type,
            "equinox": f"{birth.equinox}_of_date",
        },
        "input": {
            "latitude": birth.latitude,
            "longitude": birth.longitude,
            **tz_info,
            "utc": utc.isoformat() + "Z",
            "julian_day_ut": round(jd, 9),
        },
        "lagna": {
            **lagna.as_dict(),
            "sign_detail": _sign_block(lagna_sign),
        },
        "midheaven": angles["midheaven"].as_dict(),
        # Placidus cusps. Vedic houses are whole-sign, so these are here for KP
        # and for anyone who wants them, not used by the rest of the chart.
        "cusps": angles["cusps"],
        "grahas": grahas,
        "houses": houses,
        "aspects": _aspects(positions, lagna_sign),
        "rashi_aspects": _rashi_aspects(positions, lagna_sign),
        "sources": {
            "graha_nature": provenance.GRAHA_NATURE,
            "graha_drishti": provenance.GRAHA_DRISHTI,
            "rashi_drishti": provenance.RASHI_DRISHTI,
        },
        "panchanga": panchanga.compute(
            sun_longitude, positions["Moon"].longitude, vara_index, civil_vara_index
        ),
        "solar_day": {
            "sunrise_local": (jd_to_datetime(solar["sunrise_jd"]) + offset).isoformat(),
            "sunset_local": (jd_to_datetime(solar["sunset_jd"]) + offset).isoformat(),
            "next_sunrise_local": (
                jd_to_datetime(solar["next_sunrise_jd"]) + offset
            ).isoformat(),
            "born_before_sunrise": local.date() > vedic_day_start_local.date(),
            "sunrise_convention": birth.sunrise_convention,
        },
        "vargas": _varga_table(
            positions, lagna.longitude, vargas or ["D1", "D9", "D10", "D12", "D30"]
        ),
        "dasha": dasha,
        "current_dasha": {
            "as_of": now.isoformat(),
            "chain": active_chain(dasha, now),
        },
    }

    if include_upagrahas:
        chart["upagrahas"] = upagrahas.compute(
            jd, birth.latitude, birth.longitude, sun_longitude, lagna_sign,
            solar, vara_index, ayanamsa=birth.ayanamsa, equinox=birth.equinox,
            house_system=birth.house_system.encode(),
        )
    if include_ashtakavarga:
        chart.update(av.compute(chart))
    if include_relationships:
        chart["planet_relationship"] = maitri.compute(chart)
    if include_doshas:
        chart["doshas"] = dosha_rules.compute(chart)
    if include_calendar:
        chart.update(calendar.compute(chart))
    if include_nakshatra_info:
        # Keyed on the Moon: "your nakshatra" always means the janma star.
        chart["nakshatra_info"] = nakshatra_attributes(
            chart["grahas"]["Moon"]["nakshatra_index"])

    if include_transits:
        chart["transits"] = gochara.build(
            chart,
            birth_local=local,
            utc_offset_hours=tz_info["utc_offset_hours"],
            ayanamsa=birth.ayanamsa,
            equinox=birth.equinox,
            reference_time=now,
        )

    return chart


def summarise(chart: dict) -> str:
    """A compact text rendering, useful as a token-cheap LLM prompt header."""
    lines = [
        f"Lagna: {chart['lagna']['sign_en']} {chart['lagna']['dms']} "
        f"({chart['lagna']['nakshatra']} pada {chart['lagna']['nakshatra_pada']})",
        f"Ayanamsa: {chart['engine']['ayanamsa']} {chart['engine']['ayanamsa_degrees']:.6f}",
        "",
        "Grahas:",
    ]
    for name, g in chart["grahas"].items():
        flags = []
        if g["retrograde"]:
            flags.append("R")
        if g["dignity"]["combust"]:
            flags.append("combust")
        if g["dignity"]["state"] != "neutral":
            flags.append(g["dignity"]["state"])
        suffix = f"  [{', '.join(flags)}]" if flags else ""
        lines.append(
            f"  {name:<8} H{g['house']:<2} {g['sign_en']:<12} {g['dms']:<12} "
            f"{g['nakshatra']}-{g['nakshatra_pada']}{suffix}"
        )
    p = chart["panchanga"]
    lines += [
        "",
        f"Panchanga: {p['vara']['name']}, {p['tithi']['name']}, "
        f"{p['nakshatra']['name']}, yoga {p['yoga']['name']}, karana {p['karana']['name']}",
        "",
        "Current dasha: " + " > ".join(
            f"{c['lord']} ({c['level']})" for c in chart["current_dasha"]["chain"]
        ),
    ]
    return "\n".join(lines)
