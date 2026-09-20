"""Panchanga: the five limbs of the Vedic day.

Tithi, yoga and karana depend only on the Sun-Moon elongation, so the ayanamsa
cancels out and sidereal vs tropical longitudes give identical results.
"""

from __future__ import annotations

from .constants import (
    FIXED_KARANAS, MOVABLE_KARANAS, NAKSHATRAS, NAKSHATRA_LORDS,
    TITHI_NAMES, WEEKDAYS, YOGA_NAMES,
)

NAKSHATRA_ARC = 360.0 / 27.0


def _karana(index: int) -> str:
    """Karana 0 is Kimstughna; then seven movable karanas repeat eight times;
    the last three are fixed."""
    if index == 0:
        return FIXED_KARANAS[3]
    if index >= 57:
        return FIXED_KARANAS[index - 57]
    return MOVABLE_KARANAS[(index - 1) % 7]


def compute(
    sun_longitude: float,
    moon_longitude: float,
    vara_index: int,
    civil_vara_index: int | None = None,
) -> dict:
    elongation = (moon_longitude - sun_longitude) % 360.0

    tithi_index = int(elongation / 12.0)
    tithi_fraction = (elongation % 12.0) / 12.0

    nak_index = int((moon_longitude % 360.0) / NAKSHATRA_ARC)
    nak_fraction = ((moon_longitude % 360.0) % NAKSHATRA_ARC) / NAKSHATRA_ARC

    yoga_total = (sun_longitude + moon_longitude) % 360.0
    yoga_index = int(yoga_total / NAKSHATRA_ARC)

    karana_index = int(elongation / 6.0)

    return {
        "tithi": {
            "index": tithi_index + 1,
            "name": TITHI_NAMES[tithi_index],
            "paksha": "Shukla" if tithi_index < 15 else "Krishna",
            "elapsed_fraction": round(tithi_fraction, 6),
        },
        "nakshatra": {
            "index": nak_index + 1,
            "name": NAKSHATRAS[nak_index],
            "lord": NAKSHATRA_LORDS[nak_index],
            "pada": int(nak_fraction * 4) + 1,
            "elapsed_fraction": round(nak_fraction, 6),
        },
        "yoga": {
            "index": yoga_index + 1,
            "name": YOGA_NAMES[yoga_index],
        },
        "karana": {
            "index": karana_index + 1,
            "name": _karana(karana_index),
        },
        "vara": {
            "index": vara_index,
            "name": WEEKDAYS[vara_index],
            "basis": "sunrise",
            "note": (
                "Traditional Jyotisha: the Vedic day runs sunrise to sunrise, so a "
                "birth before sunrise belongs to the previous day's vara. Use this "
                "one for interpretation."
            ),
        },
        "civil_vara": {
            "index": civil_vara_index if civil_vara_index is not None else vara_index,
            "name": WEEKDAYS[
                civil_vara_index if civil_vara_index is not None else vara_index
            ],
            "basis": "calendar_date",
            "note": (
                "Weekday of the calendar date. Differs from `vara` for pre-sunrise "
                "births. Prokerala's daily panchang reports this one."
            ),
        },
        "sun_moon_elongation": round(elongation, 6),
    }
