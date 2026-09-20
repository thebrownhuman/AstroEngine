"""Assembles one complete, deterministic birth chart.

The output of `build()` is the only thing an LLM should ever see. The model
interprets these numbers; it never computes them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from . import ashtakavarga as av
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

ENGINE_VERSION = "1.0.0"

# Classical graha drishti, expressed as house counts from the occupied house.
SPECIAL_ASPECTS = {
    "Mars": (4, 7, 8),
    "Jupiter": (5, 7, 9),
    "Saturn": (3, 7, 10),
    "Rahu": (5, 7, 9),
    "Ketu": (5, 7, 9),
}
DEFAULT_ASPECTS = (7,)

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
    """Rashi-level graha drishti: which houses and planets each graha aspects."""
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
    angles = sky.angles(birth.latitude, birth.longitude, birth.house_system.encode())
    lagna = angles["ascendant"]
    lagna_sign = lagna.sign_index

    sun_longitude = positions["Sun"].longitude

    offset = timedelta(hours=tz_info["utc_offset_hours"])
    solar = sun_rise_set(
        jd, birth.latitude, birth.longitude, convention=birth.sunrise_convention
    )
    vedic_day_start_local = jd_to_datetime(solar["sunrise_jd"]) + offset
    # Python's weekday() is Monday=0; the vara list is Sunday=0.
    vara_index = (vedic_day_start_local.weekday() + 1) % 7
    civil_vara_index = (local.weekday() + 1) % 7

    grahas = {}
    for name, pos in positions.items():
        entry = pos.as_dict()
        entry["house"] = _house_of(pos.sign_index, lagna_sign)
        entry["dignity"] = dignity(name, pos, sun_longitude)
        entry["nature"] = (
            "benefic" if name in NATURAL_BENEFICS
            else "malefic" if name in NATURAL_MALEFICS
            else "neutral"
        )
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
    now = reference_time or datetime.now()

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
