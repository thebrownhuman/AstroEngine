"""Shadbala and bhava bala: how strong each graha and each house is.

The six strengths of BPHS Chapter 27, worked the way B. V. Raman works them in
*Graha and Bhava Balas* (he follows Sripati where Parashara is terse):

    sthana   uchcha, saptavargaja, ojayugma, kendra, drekkana
    dig      distance from the powerless cardinal point
    kala     nathonnata, paksha, tribhaga, abda/masa/vara/hora, ayana, yuddha
    chesta   from the seeghrochcha, mean and true longitudes
    naisargika
    drik     a quarter of the net drishti pinda

then the totals, the minimum-required ratio, ishta/kashta phala, and bhava
bala (bhavadhipati + bhava dig + bhava drishti).

Everything is in virupas (shashtiamsas); 60 virupas make a rupa.

`compute()` is pure arithmetic on numbers, so it can be fed Raman's printed
Standard Horoscope directly (tests/test_shadbala.py). `from_chart()` derives
those numbers from a built chart. Where the texts disagree the default
`convention="raman"` follows Raman; `convention="bphs"` switches to the
Santhanam reading of BPHS on the four points listed in
docs/shadbala-notes.md.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta

from . import provenance
from .constants import EXALTATION, MOOLATRIKONA, SIGN_LORDS
from .relationships import (
    ENEMY, EXTREME_ENEMY, EXTREME_FRIEND, FRIEND, NEUTRAL,
    compound, natural, temporal,
)
from .vargas import (
    d1_rashi, d2_hora, d3_drekkana, d7_saptamsa, d9_navamsa,
    d12_dwadasamsa, d30_trimsamsa,
)

PLANETS = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")
CONVENTIONS = ("raman", "bphs")

RAMAN = "B. V. Raman, Graha and Bhava Balas"
BPHS_27 = "BPHS Chapter 27 (Santhanam)"

# --- sthana bala --------------------------------------------------------------

DEBILITATION = {
    name: (sign * 30.0 + degree + 180.0) % 360.0
    for name, (sign, degree) in EXALTATION.items() if name in PLANETS
}

OWN = "own"
MOOLATRIKONA_GRADE = "moolatrikona"
SAPTAVARGA_VIRUPAS = {
    # Raman Art. 30 halves each step; Santhanam's BPHS 27.2-4 gives 20/15/10/4/2.
    "raman": {MOOLATRIKONA_GRADE: 45.0, OWN: 30.0, EXTREME_FRIEND: 22.5,
              FRIEND: 15.0, NEUTRAL: 7.5, ENEMY: 3.75, EXTREME_ENEMY: 1.875},
    "bphs": {MOOLATRIKONA_GRADE: 45.0, OWN: 30.0, EXTREME_FRIEND: 20.0,
             FRIEND: 15.0, NEUTRAL: 10.0, ENEMY: 4.0, EXTREME_ENEMY: 2.0},
}
SAPTAVARGAS = (
    ("D1", d1_rashi), ("D2", d2_hora), ("D3", d3_drekkana), ("D7", d7_saptamsa),
    ("D9", d9_navamsa), ("D12", d12_dwadasamsa), ("D30", d30_trimsamsa),
)

EVEN_SIGN_PLANETS = frozenset({"Moon", "Venus"})

# Drekkana (0, 1, 2) in which each planet earns 15 virupas.
DREKKANA_STRONG = {
    # Raman Art. 36: male first, hermaphrodite middle, female last.
    "raman": {"Sun": 0, "Mars": 0, "Jupiter": 0, "Mercury": 1, "Saturn": 1,
              "Moon": 2, "Venus": 2},
    # Santhanam BPHS 27.6 notes: female second, eunuch third.
    "bphs": {"Sun": 0, "Mars": 0, "Jupiter": 0, "Moon": 1, "Venus": 1,
             "Mercury": 2, "Saturn": 2},
}

# --- dig bala -----------------------------------------------------------------

# Cardinal point (0 = Lagna, 1 = IC, 2 = descendant, 3 = MC) where the planet
# has no dig bala: the one opposite its point of full strength.
DIG_POWERLESS = {"Sun": 1, "Mars": 1, "Jupiter": 2, "Mercury": 2,
                 "Moon": 3, "Venus": 3, "Saturn": 0}

# --- kala bala ----------------------------------------------------------------

DAY_STRONG = frozenset({"Sun", "Jupiter", "Venus"})
NIGHT_STRONG = frozenset({"Moon", "Mars", "Saturn"})

TRIBHAGA_DAY = ("Mercury", "Sun", "Saturn")
TRIBHAGA_NIGHT = ("Moon", "Venus", "Mars")

WEEKDAY_LORDS = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")
# Chaldean order: each hora's lord is the next one down this list.
HORA_ORDER = ("Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon")

ABDA, MASA, VARA, HORA = 15.0, 30.0, 45.0, 60.0

# Raman Art. 64: condensed ahargana = days since 1 Jan 1900 + 26,543; it counts
# its remainders from Wednesday (the weekday of his 1827 epoch).
AHARGANA_OFFSET = 26543
AHARGANA_FIRST_WEEKDAY = 3  # Wednesday, Sunday = 0

# Raman Art. 73: cumulative declination (arc-minutes) at each 15 degrees of
# bhuja, the Surya Siddhanta table with 24 degrees as the greatest kranti.
KRANTI_STEPS = (0, 362, 703, 1002, 1238, 1388, 1440)
MAX_KRANTI = 24.0
NORTH_ADDS = frozenset({"Sun", "Mars", "Jupiter", "Venus"})
SOUTH_ADDS = frozenset({"Moon", "Saturn"})

# Raman Art. 77, in seconds of arc.
BIMBA = {"Mars": 9.4, "Mercury": 6.6, "Jupiter": 190.4, "Venus": 16.6,
         "Saturn": 158.0}
WAR_ORB = 1.0

# --- chesta bala --------------------------------------------------------------

# Raman Arts. 88-103 (after Kedarnath Dutt's Book of Fate): mean longitudes at
# 0h, 1 Jan 1900, Ujjain (76 E), daily motions read off his Tables IV-IX, and
# the secular corrections in t = year - 1900.
UJJAIN_LONGITUDE = 76.0
EPOCH_JD = 2415020.5
MEAN_SUN = (257.4568, 0.98560265)
MEAN_MARS = (270.22, 0.52402)
MEAN_JUPITER = (220.04, 0.08309667)
MEAN_SATURN = (236.74, 0.033444)
SEEGHRA_MERCURY = (164.0, 4.092318)
SEEGHRA_VENUS = (328.51, 1.6021467)

# --- naisargika, drik, totals -------------------------------------------------

NAISARGIKA = {name: 60.0 * rank / 7.0 for rank, name in enumerate(
    ("Saturn", "Mars", "Mercury", "Jupiter", "Venus", "Moon", "Sun"), start=1)}

# Raman Art. 115: special aspects and the virupas they add.
VISESHA = {"Mars": ((90.0, 120.0), (210.0, 240.0), 15.0),
           "Jupiter": ((120.0, 150.0), (240.0, 270.0), 30.0),
           "Saturn": ((60.0, 90.0), (270.0, 300.0), 45.0)}

# BPHS 27.32-33 (Raman's summary), virupas.
REQUIRED = {"Sun": 300.0, "Moon": 360.0, "Mars": 300.0, "Mercury": 420.0,
            "Jupiter": 390.0, "Venus": 330.0, "Saturn": 300.0}

# --- bhava bala ---------------------------------------------------------------

NARA, JALACHARA, CHATUSHPADA, KEETA = "nara", "jalachara", "chatushpada", "keeta"
# Raman Art. 131: the bhava (1-based) at which each sign class has no
# strength; it gains 10 virupas per bhava away from it, 60 opposite.
BHAVA_DIG_ZERO = {KEETA: 1, CHATUSHPADA: 4, NARA: 7, JALACHARA: 10}
FULL_DRISHTI_ON_BHAVA = frozenset({"Jupiter", "Mercury"})

# --- provenance ---------------------------------------------------------------

SOURCES = {
    "uchcha": provenance.block(provenance.BPHS,
        f"{BPHS_27}, sloka 1: (longitude - debilitation), reduced below 180, "
        f"divided by 3. {RAMAN}, Art. 20, Example 3."),
    "saptavargaja": provenance.block(provenance.BPHS,
        f"{BPHS_27}, slokas 2-4: relationship with the lords of the seven "
        f"vargas, moolatrikona counted in the rasi only. Grade values follow "
        f"{RAMAN}, Art. 30 (45/30/22.5/15/7.5/3.75/1.875); Santhanam gives "
        "20/15/10/4/2 for the friend-to-enemy grades."),
    "ojayugma": provenance.block(provenance.BPHS,
        f"{BPHS_27}, sloka 4: the Moon and Venus in even, the rest in odd "
        f"rasi and navamsa, 15 virupas each. {RAMAN}, Art. 31."),
    "kendra": provenance.block(provenance.BPHS,
        f"{BPHS_27}, sloka 5: kendra 60, panapara 30, apoklima 15, by sign. "
        f"{RAMAN}, Arts. 32-35."),
    "drekkana": provenance.block(provenance.BPHS,
        f"{BPHS_27}, sloka 6: 15 virupas by the sex of the planet and the "
        f"decanate. Assignment follows {RAMAN}, Art. 36 (hermaphrodite middle, "
        "female last); Santhanam's notes reverse those two."),
    "dig": provenance.block(provenance.BPHS,
        f"{BPHS_27}, slokas 7-7.5: arc from the powerless cardinal point, "
        f"reduced below 180, divided by 3. {RAMAN}, Arts. 41-45."),
    "nathonnata": provenance.block(provenance.BPHS,
        f"{BPHS_27}, slokas 8-9: from local apparent time; Mercury always 60. "
        f"{RAMAN}, Art. 51 (method B)."),
    "paksha": provenance.block(provenance.BPHS,
        f"{BPHS_27}, slokas 10-11: Sun-Moon elongation / 3 for benefics, 60 "
        f"less that for malefics, the Moon's doubled. {RAMAN}, Arts. 52-55."),
    "tribhaga": provenance.block(provenance.BPHS,
        f"{BPHS_27}, sloka 12: Mercury, Sun, Saturn rule the thirds of the "
        f"day; Moon, Venus, Mars of the night; Jupiter always 60. "
        f"{RAMAN}, Arts. 56-57."),
    "abda_masa_vara_hora": provenance.block(provenance.BPHS,
        f"{BPHS_27}, sloka 13: 15, 30, 45 and 60 virupas to the lords of the "
        f"year, month, weekday and hora. Lords from the ahargana and equal "
        f"one-hour horas from sunrise, {RAMAN}, Arts. 58-70."),
    "ayana": provenance.block(provenance.BPHS,
        f"{BPHS_27}, slokas 15-17: (24 +/- kranti) / 48 x 60, doubled for the "
        f"Sun. Kranti from the sayana longitude by the 24-degree tabular sine, "
        f"{RAMAN}, Arts. 71-75 (Kesava's formula)."),
    "yuddha": provenance.block(provenance.CLASSICAL,
        f"{RAMAN}, Arts. 76-77 (Sripati): planets Mars-Saturn within 1 degree; "
        "the one of lesser longitude wins; the difference of their sthana + "
        "dig + kala (to hora) divided by the difference of disc diameters. "
        f"{BPHS_27}, sloka 20 transfers the plain difference of shadbalas."),
    "chesta": provenance.block(provenance.BPHS,
        f"{BPHS_27}, slokas 24-25: seeghrochcha - (mean + true) / 2, reduced "
        f"below 180, divided by 3. Mean longitudes and seeghrochchas from "
        f"{RAMAN}, Arts. 88-107. For the Sun and Moon, sloka 18 makes ayana and "
        "paksha bala their chesta; Raman's totals (Example 56) leave it out, "
        "and the default here follows him."),
    "naisargika": provenance.block(provenance.BPHS,
        f"{BPHS_27}, sloka 14: 60/7 x rank, Saturn 1 to the Sun 7. "
        f"{RAMAN}, Art. 108."),
    "drik": provenance.block(provenance.BPHS,
        f"{BPHS_27}, sloka 19: a quarter of the drishti pinda, benefic aspects "
        f"adding and malefic subtracting. Drishti values and special aspects "
        f"(Mars 15, Jupiter 30, Saturn 45) from {RAMAN}, Arts. 109-120 "
        "(Sripati)."),
    "totals": provenance.block(provenance.BPHS,
        f"{BPHS_27}, slokas 32-33: required shadbala 300/360/300/420/390/330/300 "
        f"virupas, Sun to Saturn. {RAMAN}, Arts. 121-122."),
    "ishta_kashta": provenance.block(provenance.CLASSICAL,
        f"{RAMAN}, Ch. X (Sripati): ishta = sqrt(uchcha x chesta), kashta = "
        "sqrt((60 - uchcha)(60 - chesta)); the Sun's chesta from sayana + 90, "
        "the Moon's from the elongation. BPHS Chapter 28 derives them from "
        "rasmis instead."),
    "bhava_bala": provenance.block(provenance.BPHS,
        "BPHS Chapter 27, slokas 26-29: lord's shadbala + bhava dig bala + "
        f"bhava drishti. {RAMAN}, Ch. IX: Sripati bhava madhyas, a quarter of "
        "each aspect but the whole of Jupiter's and Mercury's, Mercury always "
        "benefic."),
}


# --- helpers ------------------------------------------------------------------

def _reduce(arc: float) -> float:
    """An arc folded into 0-180."""
    arc %= 360.0
    return 360.0 - arc if arc > 180.0 else arc


def _r(value: float) -> float:
    return round(value, 2)


def drishti_value(kendra: float) -> float:
    """Raman Art. 114: the aspect value (virupas) at a drishti kendra."""
    k = kendra % 360.0
    if k < 30.0 or k >= 300.0:
        return 0.0
    if k < 60.0:
        return (k - 30.0) / 2.0
    if k < 90.0:
        return k - 60.0 + 15.0
    if k < 120.0:
        return (120.0 - k) / 2.0 + 30.0
    if k < 150.0:
        return 150.0 - k
    if k < 180.0:
        return (k - 150.0) * 2.0
    return (300.0 - k) / 2.0


def visesha(planet: str, kendra: float) -> float:
    if planet not in VISESHA:
        return 0.0
    first, second, extra = VISESHA[planet]
    k = kendra % 360.0
    return extra if any(lo <= k < hi for lo, hi in (first, second)) else 0.0


def full_drishti(aspecting: str, aspecting_longitude: float, target: float) -> float:
    kendra = (target - aspecting_longitude) % 360.0
    return drishti_value(kendra) + visesha(aspecting, kendra)


def sripati_madhyas(ascendant: float, midheaven: float) -> list[float]:
    """Bhava madhyas 1-12: the Lagna, IC, descendant and MC, with each
    quadrant trisected."""
    cardinal = [ascendant, (midheaven + 180.0) % 360.0,
                (ascendant + 180.0) % 360.0, midheaven]
    madhyas = []
    for i in range(4):
        start, end = cardinal[i], cardinal[(i + 1) % 4]
        step = ((end - start) % 360.0) / 3.0
        madhyas += [(start + step * j) % 360.0 for j in range(3)]
    return madhyas


def kranti(sayana: float) -> float:
    """Signed declination in degrees (north positive), Raman Art. 73."""
    s = sayana % 360.0
    bhuja = s % 180.0
    if bhuja > 90.0:
        bhuja = 180.0 - bhuja
    step = min(int(bhuja / 15.0), 5)
    minutes = KRANTI_STEPS[step] + (bhuja - 15.0 * step) / 15.0 * (
        KRANTI_STEPS[step + 1] - KRANTI_STEPS[step])
    return minutes / 60.0 if s < 180.0 else -minutes / 60.0


def _mercury_is_malefic(longitudes: dict) -> bool:
    """Mercury joined (same sign) with the Sun, Mars or Saturn."""
    sign = int(longitudes["Mercury"] / 30.0)
    return any(int(longitudes[p] / 30.0) == sign for p in ("Sun", "Mars", "Saturn"))


def natures(longitudes: dict) -> dict:
    """Benefic (True) or malefic for paksha and drik bala (Raman Arts. 53, 117)."""
    elongation = (longitudes["Moon"] - longitudes["Sun"]) % 360.0
    return {
        "Sun": False, "Mars": False, "Saturn": False,
        "Jupiter": True, "Venus": True,
        "Moon": 0.0 < elongation < 180.0,
        "Mercury": not _mercury_is_malefic(longitudes),
    }


# --- moment -------------------------------------------------------------------

@dataclass(frozen=True)
class Moment:
    """The time-dependent inputs to kala and chesta bala.

    apparent_hours: local apparent time, hours after midnight.
    is_day / part_fraction: birth between sunrise and sunset, and how far
        through that day (or night) it falls, 0-1.
    hours_since_sunrise: for the hora lord.
    ahargana: Raman's condensed ahargana for the Vedic (sunrise) date.
    chesta_interval: days since 0h 1 Jan 1900, Ujjain mean time.
    year: the civil year, for the secular corrections.
    """
    apparent_hours: float
    is_day: bool
    part_fraction: float
    hours_since_sunrise: float
    ahargana: int
    chesta_interval: float
    year: int


def ahargana_for(vedic_date: date) -> int:
    return (vedic_date - date(1900, 1, 1)).days + AHARGANA_OFFSET


def _counted_weekday(remainder: int) -> int:
    """Raman counts a remainder r as the r-th day starting from Wednesday."""
    return (AHARGANA_FIRST_WEEKDAY + remainder - 1) % 7


def lords_of_time(moment: Moment) -> dict:
    a = moment.ahargana
    vara = _counted_weekday(a % 7)
    weekday_lord = WEEKDAY_LORDS[vara]
    elapsed = int(moment.hours_since_sunrise)
    hora = HORA_ORDER[(HORA_ORDER.index(weekday_lord) + elapsed) % 7]
    return {
        "abda": WEEKDAY_LORDS[_counted_weekday(((a // 360) * 3 + 1) % 7)],
        "masa": WEEKDAY_LORDS[_counted_weekday(((a // 30) * 2 + 1) % 7)],
        "vara": weekday_lord,
        "hora": hora,
    }


def mean_positions(moment: Moment) -> dict:
    """Mean longitudes and seeghrochchas (Raman Arts. 94-104)."""
    i, t = moment.chesta_interval, moment.year - 1900

    def mean(epoch_rate: tuple[float, float], correction: float = 0.0) -> float:
        epoch, rate = epoch_rate
        return (epoch + rate * i + correction) % 360.0

    sun = mean(MEAN_SUN)
    return {
        "mean": {
            "Mars": mean(MEAN_MARS),
            "Mercury": sun,
            "Jupiter": mean(MEAN_JUPITER, -(3.33 + 0.0067 * t)),
            "Venus": sun,
            "Saturn": mean(MEAN_SATURN, 5.0 + 0.001 * t),
        },
        "seeghrochcha": {
            "Mars": sun, "Jupiter": sun, "Saturn": sun,
            "Mercury": mean(SEEGHRA_MERCURY, 6.67 - 0.00133 * t),
            "Venus": mean(SEEGHRA_VENUS, -(5.0 + 0.001 * t)),
        },
    }


# --- the components -----------------------------------------------------------

def uchcha_bala(planet: str, longitude: float) -> float:
    return _reduce(longitude - DEBILITATION[planet]) / 3.0


def _in_moolatrikona(planet: str, longitude: float) -> bool:
    sign, start, end = MOOLATRIKONA[planet]
    return int(longitude / 30.0) == sign and start <= longitude % 30.0 < end


def saptavarga_grades(planet: str, longitudes: dict) -> dict:
    rasi_signs = {p: int(lon / 30.0) for p, lon in longitudes.items()}
    grades = {}
    for label, varga in SAPTAVARGAS:
        lord = SIGN_LORDS[varga(longitudes[planet])]
        if label == "D1" and _in_moolatrikona(planet, longitudes[planet]):
            grades[label] = MOOLATRIKONA_GRADE
        elif lord == planet:
            grades[label] = OWN
        else:
            grades[label] = compound(
                natural(planet, lord),
                temporal(rasi_signs[planet], rasi_signs[lord]))
    return grades


def ojayugma_bala(planet: str, longitude: float) -> float:
    wants_even = planet in EVEN_SIGN_PLANETS
    score = 0.0
    for sign in (d1_rashi(longitude), d9_navamsa(longitude)):
        if (sign % 2 == 1) == wants_even:
            score += 15.0
    return score


def kendra_bala(longitude: float, lagna_longitude: float) -> float:
    house = (int(longitude / 30.0) - int(lagna_longitude / 30.0)) % 12 + 1
    return 60.0 if house % 3 == 1 else 30.0 if house % 3 == 2 else 15.0


def drekkana_bala(planet: str, longitude: float, convention: str) -> float:
    return 15.0 if int((longitude % 30.0) / 10.0) == DREKKANA_STRONG[convention][planet] else 0.0


def dig_bala(planet: str, longitude: float, ascendant: float, midheaven: float) -> float:
    cardinal = (ascendant, (midheaven + 180.0) % 360.0,
                (ascendant + 180.0) % 360.0, midheaven)
    return _reduce(longitude - cardinal[DIG_POWERLESS[planet]]) / 3.0


def nathonnata_bala(planet: str, apparent_hours: float) -> float:
    if planet == "Mercury":
        return 60.0
    from_midnight = _reduce(apparent_hours * 15.0)
    diva = from_midnight / 3.0
    return diva if planet in DAY_STRONG else 60.0 - diva


def paksha_values(longitudes: dict) -> tuple[float, float]:
    """(benefic value, malefic value), Raman Art. 55."""
    subha = _reduce(longitudes["Moon"] - longitudes["Sun"]) / 3.0
    return subha, 60.0 - subha


def tribhaga_bala(planet: str, moment: Moment) -> float:
    if planet == "Jupiter":
        return 60.0
    part = min(int(moment.part_fraction * 3.0), 2)
    rulers = TRIBHAGA_DAY if moment.is_day else TRIBHAGA_NIGHT
    return 60.0 if rulers[part] == planet else 0.0


def ayana_bala(planet: str, sayana: float) -> tuple[float, float]:
    """(ayana bala, kranti). The Sun's value is already doubled."""
    k = kranti(sayana)
    if planet == "Mercury" or (planet in NORTH_ADDS) == (k >= 0.0):
        signed = abs(k)
    else:
        signed = -abs(k)
    value = (MAX_KRANTI + signed) / (2 * MAX_KRANTI) * 60.0
    return (value * 2.0 if planet == "Sun" else value), k


def chesta_kendra(planet: str, longitude: float, means: dict) -> float:
    true_plus_mean = (means["mean"][planet] + longitude) / 2.0
    # Average the two on the short arc so a pair either side of 0 Aries works.
    if abs(means["mean"][planet] - longitude) > 180.0:
        true_plus_mean += 180.0
    return (means["seeghrochcha"][planet] - true_plus_mean) % 360.0


def drik_pinda(target: str, longitudes: dict, benefic: dict) -> tuple[float, float]:
    """(benefic drishti, malefic drishti) cast on a graha."""
    good = bad = 0.0
    for source in PLANETS:
        if source == target:
            continue
        value = full_drishti(source, longitudes[source], longitudes[target])
        if benefic[source]:
            good += value
        else:
            bad += value
    return good, bad


def bhava_dig_class(madhya: float) -> str:
    sign, degree = int(madhya / 30.0), madhya % 30.0
    if sign == 7:
        return KEETA
    if sign in (2, 5, 6, 10) or (sign == 8 and degree < 15.0):
        return NARA
    if sign in (3, 11) or (sign == 9 and degree >= 15.0):
        return JALACHARA
    return CHATUSHPADA  # Aries, Taurus, Leo, Sagittarius 15-30, Capricorn 0-15


def bhava_dig_bala(bhava: int, madhya: float) -> float:
    distance = abs(BHAVA_DIG_ZERO[bhava_dig_class(madhya)] - bhava) % 12
    return 10.0 * min(distance, 12 - distance)


# --- assembly -----------------------------------------------------------------

def compute(
    longitudes: dict,
    *,
    ayanamsa: float,
    ascendant: float,
    midheaven: float,
    moment: Moment,
    bhava_madhyas: list[float] | None = None,
    convention: str = "raman",
) -> dict:
    """Shadbala and bhava bala from nirayana longitudes and the moment."""
    if convention not in CONVENTIONS:
        raise ValueError(f"unknown convention {convention!r}; expected one of {CONVENTIONS}")
    lon = {p: longitudes[p] % 360.0 for p in PLANETS}
    benefic = natures(lon)
    subha, papa = paksha_values(lon)
    lords = lords_of_time(moment)
    means = mean_positions(moment)
    values = SAPTAVARGA_VIRUPAS[convention]

    planets = {}
    for p in PLANETS:
        grades = saptavarga_grades(p, lon)
        sthana = {
            "uchcha": uchcha_bala(p, lon[p]),
            "saptavargaja": sum(values[g] for g in grades.values()),
            "ojayugma": ojayugma_bala(p, lon[p]),
            "kendra": kendra_bala(lon[p], ascendant),
            "drekkana": drekkana_bala(p, lon[p], convention),
        }
        ayana, decl = ayana_bala(p, lon[p] + ayanamsa)
        paksha = subha if (p == "Moon" or benefic[p]) else papa
        if p == "Moon":
            paksha *= 2.0
        kala = {
            "nathonnata": nathonnata_bala(p, moment.apparent_hours),
            "paksha": paksha,
            "tribhaga": tribhaga_bala(p, moment),
            "abda": ABDA if lords["abda"] == p else 0.0,
            "masa": MASA if lords["masa"] == p else 0.0,
            "vara": VARA if lords["vara"] == p else 0.0,
            "hora": HORA if lords["hora"] == p else 0.0,
            "ayana": ayana,
            "yuddha": 0.0,
        }
        if p in ("Sun", "Moon"):
            kendra = None
            # Raman Ch. X: used for ishta/kashta only.
            phala_chesta = (_reduce(lon["Sun"] + ayanamsa + 90.0) / 3.0 if p == "Sun"
                            else subha)
            if convention == "bphs":
                chesta = ayana if p == "Sun" else kala["paksha"]
            else:
                chesta = 0.0
        else:
            kendra = chesta_kendra(p, lon[p], means)
            chesta = _reduce(kendra) / 3.0
            phala_chesta = chesta
        good, bad = drik_pinda(p, lon, benefic)
        planets[p] = {
            "sthana": sthana,
            "saptavarga_grades": grades,
            "dig": dig_bala(p, lon[p], ascendant, midheaven),
            "kala": kala,
            "kranti": decl,
            "chesta": chesta,
            "chesta_kendra": kendra,
            "phala_chesta": phala_chesta,
            "naisargika": NAISARGIKA[p],
            "drishti_pinda": good - bad,
            "drik": (good - bad) / 4.0,
        }

    _apply_yuddha(planets, lon, convention)

    out = {}
    for p, b in planets.items():
        sthana_total = sum(b["sthana"].values())
        kala_total = sum(b["kala"].values())
        total = sthana_total + b["dig"] + kala_total + b["chesta"] + b["naisargika"] + b["drik"]
        uchcha = b["sthana"]["uchcha"]
        out[p] = {
            "sthana": {**{k: _r(v) for k, v in b["sthana"].items()}, "total": _r(sthana_total)},
            "saptavarga_grades": b["saptavarga_grades"],
            "dig": _r(b["dig"]),
            "kala": {**{k: _r(v) for k, v in b["kala"].items()}, "total": _r(kala_total),
                     "kranti_degrees": _r(b["kranti"])},
            "chesta": _r(b["chesta"]),
            **({"chesta_kendra": _r(b["chesta_kendra"])} if b["chesta_kendra"] is not None else {}),
            "naisargika": _r(b["naisargika"]),
            "drishti_pinda": _r(b["drishti_pinda"]),
            "drik": _r(b["drik"]),
            "total_virupas": _r(total),
            "total_rupas": _r(total / 60.0),
            "required_virupas": REQUIRED[p],
            "strength_ratio": _r(total / REQUIRED[p]),
            "is_strong": total >= REQUIRED[p],
            "ishta_phala": _r(math.sqrt(uchcha * b["phala_chesta"])),
            "kashta_phala": _r(math.sqrt((60.0 - uchcha) * (60.0 - b["phala_chesta"]))),
            "_total": total,
        }
    ranked = sorted(PLANETS, key=lambda p: out[p]["strength_ratio"], reverse=True)
    for rank, p in enumerate(ranked, start=1):
        out[p]["rank"] = rank

    madhyas = bhava_madhyas or sripati_madhyas(ascendant, midheaven)
    bhavas = bhava_bala(madhyas, lon, {p: out[p]["_total"] for p in PLANETS}, benefic)
    for p in PLANETS:
        del out[p]["_total"]

    return {
        "convention": convention,
        "unit": "virupa (shashtiamsa); 60 virupas = 1 rupa",
        "lords_of_time": lords,
        "planets": out,
        "bhavas": bhavas,
        "sources": SOURCES,
    }


def _apply_yuddha(planets: dict, lon: dict, convention: str) -> None:
    fighters = [p for p in PLANETS if p not in ("Sun", "Moon")]

    def aggregate(p: str) -> float:
        b = planets[p]
        if convention == "bphs":
            # Sloka 20 moves the difference of the shadbalas; drik is included.
            return (sum(b["sthana"].values()) + b["dig"] + sum(b["kala"].values())
                    + b["chesta"] + b["naisargika"] + b["drik"])
        kala_to_hora = sum(v for k, v in b["kala"].items() if k not in ("ayana", "yuddha"))
        return sum(b["sthana"].values()) + b["dig"] + kala_to_hora

    before = {p: aggregate(p) for p in fighters}
    for i, a in enumerate(fighters):
        for b in fighters[i + 1:]:
            gap = (lon[b] - lon[a]) % 360.0
            if min(gap, 360.0 - gap) >= WAR_ORB:
                continue
            # The one of lesser longitude (behind on the short arc) wins.
            winner, loser = (a, b) if gap < 180.0 else (b, a)
            difference = abs(before[a] - before[b])
            if convention == "raman":
                difference /= abs(BIMBA[a] - BIMBA[b])
            planets[winner]["kala"]["yuddha"] += difference
            planets[loser]["kala"]["yuddha"] -= difference


def bhava_bala(madhyas: list[float], lon: dict, shadbala: dict, benefic: dict) -> list[dict]:
    rows = []
    for index, madhya in enumerate(madhyas):
        bhava = index + 1
        lord = SIGN_LORDS[int(madhya / 30.0)]
        drishti = 0.0
        for source in PLANETS:
            value = full_drishti(source, lon[source], madhya)
            if source not in FULL_DRISHTI_ON_BHAVA:
                value /= 4.0
            # Raman Ch. IX note: Mercury counts as a full benefic here.
            good = True if source == "Mercury" else benefic[source]
            drishti += value if good else -value
        dig = bhava_dig_bala(bhava, madhya)
        total = shadbala[lord] + dig + drishti
        rows.append({
            "bhava": bhava,
            "madhya": round(madhya, 4),
            "lord": lord,
            "bhavadhipati": _r(shadbala[lord]),
            "dig": _r(dig),
            "dig_class": bhava_dig_class(madhya),
            "drishti": _r(drishti),
            "total_virupas": _r(total),
            "total_rupas": _r(total / 60.0),
        })
    ranked = sorted(rows, key=lambda r: r["total_virupas"], reverse=True)
    for rank, row in enumerate(ranked, start=1):
        row["rank"] = rank
    return rows


# --- from a built chart -------------------------------------------------------

def moment_for(jd_ut: float, latitude: float, longitude: float,
               sunrise_convention: str = "apparent") -> Moment:
    import swisseph as swe

    from .ephemeris import jd_to_datetime, sun_rise_set

    solar = sun_rise_set(jd_ut, latitude, longitude, convention=sunrise_convention)
    lmt_offset = longitude / 360.0
    equation = swe.time_equ(jd_ut)
    if isinstance(equation, tuple):
        equation = equation[0]
    apparent_hours = ((jd_ut + 0.5 + lmt_offset + equation) % 1.0) * 24.0
    is_day = jd_ut < solar["sunset_jd"]
    if is_day:
        start, end = solar["sunrise_jd"], solar["sunset_jd"]
    else:
        start, end = solar["sunset_jd"], solar["next_sunrise_jd"]
    vedic_date = jd_to_datetime(solar["sunrise_jd"] + lmt_offset).date()
    return Moment(
        apparent_hours=apparent_hours,
        is_day=is_day,
        part_fraction=(jd_ut - start) / (end - start),
        hours_since_sunrise=(jd_ut - solar["sunrise_jd"]) * 24.0,
        ahargana=ahargana_for(vedic_date),
        chesta_interval=jd_ut + UJJAIN_LONGITUDE / 360.0 - EPOCH_JD,
        year=jd_to_datetime(jd_ut + lmt_offset).year,
    )


def from_chart(chart: dict, convention: str = "raman") -> dict:
    """Shadbala for a chart built by chart.build(). Raises ValueError where
    the Sun does not rise or set (kala bala needs the day's length)."""
    inputs = chart["input"]
    sunrise_convention = (chart.get("solar_day") or {}).get("sunrise_convention", "apparent")
    moment = moment_for(inputs["julian_day_ut"], inputs["latitude"], inputs["longitude"],
                        sunrise_convention)
    result = compute(
        {p: chart["grahas"][p]["longitude"] for p in PLANETS},
        ayanamsa=chart["engine"]["ayanamsa_degrees"],
        ascendant=chart["lagna"]["longitude"],
        midheaven=chart["midheaven"]["longitude"],
        moment=moment,
        convention=convention,
    )
    result["bhava_madhya_convention"] = "sripati"
    return result
