"""Divisional (varga) charts per Brihat Parashara Hora Shastra.

Every function maps an absolute sidereal longitude to a varga sign index 0-11.
Signs are 0-indexed from Mesha/Aries.
"""

from __future__ import annotations

MOVABLE, FIXED, DUAL = 0, 1, 2
FIRE, EARTH, AIR, WATER = 0, 1, 2, 3


def _parts(longitude: float) -> tuple[int, float]:
    longitude %= 360.0
    return int(longitude / 30.0), longitude % 30.0


def _modality(sign: int) -> int:
    return sign % 3


def _element(sign: int) -> int:
    return sign % 4


def d1_rashi(longitude: float) -> int:
    sign, _ = _parts(longitude)
    return sign


def d2_hora(longitude: float) -> int:
    sign, deg = _parts(longitude)
    odd = sign % 2 == 0  # Aries is the 1st sign, i.e. odd
    first_half = deg < 15.0
    # Odd signs: Leo then Cancer. Even signs: Cancer then Leo.
    if odd:
        return 4 if first_half else 3
    return 3 if first_half else 4


def d3_drekkana(longitude: float) -> int:
    sign, deg = _parts(longitude)
    return (sign + 4 * int(deg / 10.0)) % 12


def d4_chaturthamsa(longitude: float) -> int:
    sign, deg = _parts(longitude)
    return (sign + 3 * int(deg / 7.5)) % 12


def d7_saptamsa(longitude: float) -> int:
    sign, deg = _parts(longitude)
    start = sign if sign % 2 == 0 else (sign + 6) % 12
    return (start + int(deg / (30.0 / 7.0))) % 12


def d9_navamsa(longitude: float) -> int:
    # The continuous form is equivalent to the movable/fixed/dual start rule.
    return int((longitude % 360.0) / (30.0 / 9.0)) % 12


def d10_dasamsa(longitude: float) -> int:
    sign, deg = _parts(longitude)
    start = sign if sign % 2 == 0 else (sign + 8) % 12
    return (start + int(deg / 3.0)) % 12


def d12_dwadasamsa(longitude: float) -> int:
    sign, deg = _parts(longitude)
    return (sign + int(deg / 2.5)) % 12


def d16_shodasamsa(longitude: float) -> int:
    sign, deg = _parts(longitude)
    start = {MOVABLE: 0, FIXED: 4, DUAL: 8}[_modality(sign)]
    return (start + int(deg / 1.875)) % 12


def d20_vimsamsa(longitude: float) -> int:
    sign, deg = _parts(longitude)
    start = {MOVABLE: 0, FIXED: 8, DUAL: 4}[_modality(sign)]
    return (start + int(deg / 1.5)) % 12


def d24_siddhamsa(longitude: float) -> int:
    sign, deg = _parts(longitude)
    start = 4 if sign % 2 == 0 else 3
    return (start + int(deg / 1.25)) % 12


def d27_bhamsa(longitude: float) -> int:
    sign, deg = _parts(longitude)
    start = {FIRE: 0, EARTH: 3, AIR: 6, WATER: 9}[_element(sign)]
    return (start + int(deg / (30.0 / 27.0))) % 12


# Trimsamsa uses unequal spans ruled by the five non-luminary planets.
_D30_ODD = [(5.0, 0), (10.0, 10), (18.0, 8), (25.0, 2), (30.0, 6)]
_D30_EVEN = [(5.0, 1), (12.0, 5), (20.0, 11), (25.0, 9), (30.0, 7)]


def d30_trimsamsa(longitude: float) -> int:
    sign, deg = _parts(longitude)
    table = _D30_ODD if sign % 2 == 0 else _D30_EVEN
    for upper, varga_sign in table:
        if deg < upper:
            return varga_sign
    return table[-1][1]


def d40_khavedamsa(longitude: float) -> int:
    sign, deg = _parts(longitude)
    start = 0 if sign % 2 == 0 else 6
    return (start + int(deg / 0.75)) % 12


def d45_akshavedamsa(longitude: float) -> int:
    sign, deg = _parts(longitude)
    start = {MOVABLE: 0, FIXED: 4, DUAL: 8}[_modality(sign)]
    return (start + int(deg / (30.0 / 45.0))) % 12


def d60_shashtiamsa(longitude: float) -> int:
    sign, deg = _parts(longitude)
    return (sign + int(deg / 0.5)) % 12


VARGAS = {
    "D1": ("Rashi", d1_rashi),
    "D2": ("Hora", d2_hora),
    "D3": ("Drekkana", d3_drekkana),
    "D4": ("Chaturthamsa", d4_chaturthamsa),
    "D7": ("Saptamsa", d7_saptamsa),
    "D9": ("Navamsa", d9_navamsa),
    "D10": ("Dasamsa", d10_dasamsa),
    "D12": ("Dwadasamsa", d12_dwadasamsa),
    "D16": ("Shodasamsa", d16_shodasamsa),
    "D20": ("Vimsamsa", d20_vimsamsa),
    "D24": ("Siddhamsa", d24_siddhamsa),
    "D27": ("Bhamsa", d27_bhamsa),
    "D30": ("Trimsamsa", d30_trimsamsa),
    "D40": ("Khavedamsa", d40_khavedamsa),
    "D45": ("Akshavedamsa", d45_akshavedamsa),
    "D60": ("Shashtiamsa", d60_shashtiamsa),
}
