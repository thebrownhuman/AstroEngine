"""Ayana, ritu and the Sudarshana Chakra.

Three small things that did not belong anywhere else.

*Ayana* is which half of the year the Sun is climbing through: Uttarayana from
Makara Sankranti to Karka Sankranti, Dakshinayana the other half. Sidereal, so
it turns on Sun's sign, not on the tropical solstice.

*Ritu*, the season, comes in two flavours. The drik (observed) ritu pairs the
sidereal solar months: Makara and Kumbha are Shishir, Meena and Mesha are
Vasant, and so on. The vedic ritu pairs lunar months instead and is not
reproduced here -- see RITU_PARITY.

*Sudarshana Chakra* is the chart read three times over, counting houses from
the Lagna, from the Sun and from the Moon, so that a house can be strong from
one reference and weak from another.
"""

from __future__ import annotations

from .constants import SIGNS, SIGNS_EN, SIGN_LORDS

UTTARAYANA_SIGNS = frozenset({9, 10, 11, 0, 1, 2})   # Makara through Mithuna

# Prokerala labels the northward half "Summer Solstice / Uttarayan" and the
# southward half "Winter Solstice / Dakshinayan", naming each ayana after the
# solstice that opens it.
AYANA = {
    True: {"id": 0, "name": "Summer Solstice", "vedic_name": "Uttarayan"},
    False: {"id": 1, "name": "Winter Solstice", "vedic_name": "Dakshinayan"},
}

RITU_NAMES = [
    (0, "Spring", "Vasant"), (1, "Summer", "Grishma"), (2, "Monsoon", "Varsha"),
    (3, "Autumn", "Sharad"), (4, "Prewinter", "Hemant"), (5, "Winter", "Shishir"),
]

# The vedic ritu runs on lunar months. Prokerala's boundaries for it came back
# exactly 59 days apart, which is neither two lunar months (59.06) nor two
# sidereal solar months (60.9), and one sample was not enough to tell what they
# actually do. Only the drik ritu is emitted.
RITU_PARITY = "drik verified; vedic not reproduced"

SUDARSHANA_REFERENCES = ("Lagna", "Sun", "Moon")


def ayana(sun_sign: int) -> dict:
    return AYANA[sun_sign in UTTARAYANA_SIGNS]


def drik_ritu(sun_sign: int) -> dict:
    """Sidereal solar months pair up into six seasons, starting at Meena."""
    index = ((sun_sign - 11) // 2) % 6
    number, name, vedic = RITU_NAMES[index]
    return {"id": number, "name": name, "vedic_name": vedic}


def _sign_block(index: int) -> dict:
    return {"index": index, "name": SIGNS[index], "name_en": SIGNS_EN[index],
            "lord": SIGN_LORDS[index]}


def sudarshana_chakra(chart: dict) -> dict:
    """The same placements counted from the Lagna, the Sun and the Moon."""
    references = {
        "Lagna": chart["lagna"]["sign_index"],
        "Sun": chart["grahas"]["Sun"]["sign_index"],
        "Moon": chart["grahas"]["Moon"]["sign_index"],
    }

    wheels = {}
    for label in SUDARSHANA_REFERENCES:
        base = references[label]
        houses = []
        for number in range(1, 13):
            sign = (base + number - 1) % 12
            houses.append({
                "house": number,
                "rasi": _sign_block(sign),
                "occupants": sorted(
                    name for name, graha in chart["grahas"].items()
                    if graha["sign_index"] == sign
                ),
            })
        wheels[label] = {"reference_rasi": _sign_block(base), "houses": houses}
    return wheels


def compute(chart: dict) -> dict:
    sun_sign = chart["grahas"]["Sun"]["sign_index"]
    return {
        "solstice": ayana(sun_sign),
        "drik_ritu": {**drik_ritu(sun_sign), "parity": RITU_PARITY},
        "sudarshana_chakra": sudarshana_chakra(chart),
    }
