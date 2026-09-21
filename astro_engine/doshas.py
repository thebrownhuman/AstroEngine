"""Kaal Sarpa and Papasamyam.

Mangal dosha lives in `yogas.kuja`, which already matches Prokerala's
/mangal-dosha verdict; these are the two remaining dosha endpoints.

**Kaal Sarpa** is present when every one of the seven grahas is hemmed inside
the arc running zodiacally from Rahu to Ketu; the twelve names come from the
house Rahu occupies. When the grahas fall on the other side instead, the yoga
is **Kaal Amrita**, which carries no type name. (Prokerala's wording is the
reverse of the arc direction -- they say "between Ketu and Rahu" for the case
this module calls forward -- because they count along Rahu's own retrograde
motion. The verdicts agree; only the phrasing is inverted.)

Measured against 18 charts spanning every Rahu house and both directions, this
reproduces 16. The two it does not are the same chart on consecutive days,
where Prokerala returns Kaal Amrita for a configuration that is unambiguously
forward and that it labels Kaal Sarpa in other years. Mean nodes fit better
than true nodes, retrogression does not explain it, and no house-based reading
separates it either; it looks like a defect on their side, so it is left
disagreeing rather than special-cased.

**Papasamyam** scores the malefics Mars, Saturn, Sun and Rahu as they stand
from three reference points -- the Lagna, the Moon and Venus. A malefic in the
1st, 2nd, 4th, 7th, 8th or 12th from a reference carries dosha there. The
The boolean grid is exact against Prokerala, and so is the `total_points`
that sits on top of it: each dosha is worth one point from the Ascendant, half
from the Moon and a quarter from Venus, regardless of which malefic it is.
"""

from __future__ import annotations
from . import provenance

# Rahu's house -> the name of the kaal sarpa form. These spellings were read
# off the live API one house at a time; several differ from the textbook ones
# (Vaasuki not Vasuki, Padam not Padma, Paatak not Ghatak, Vishakt not
# Vishdhar, Shankhchurn not Shankhachur).
KAAL_SARPA_TYPES = [
    "Anant", "Kulik", "Vaasuki", "Shankhpal", "Padam", "Mahapadam",
    "Takshak", "Karkotak", "Shankhchurn", "Paatak", "Vishakt", "Sheshnaag",
]
KAAL_SARPA_LABEL = "Kaal Sarpa"
KAAL_AMRITA_LABEL = "Kaal Amrita"

SEVEN = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")

# Papasamyam: the malefics scored, in Prokerala's order, and their ids.
PAPA_PLANETS = (("Mars", 4), ("Saturn", 6), ("Sun", 0), ("Rahu", 101))
PAPA_REFERENCES = ("Ascendant", "Moon", "Venus")
PAPA_HOUSES = frozenset({1, 2, 4, 7, 8, 12})


def _ordinal(number: int) -> str:
    if 10 <= number % 100 <= 20:
        return f"{number}th"
    return f"{number}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(number % 10, 'th') }".replace(" ", "")


def _hemmed(longitudes: dict[str, float], start: float, end: float) -> bool:
    """True when every graha lies in the arc running forward from start to end."""
    span = (end - start) % 360.0
    return all(0.0 < (longitudes[name] - start) % 360.0 < span for name in SEVEN)


def kaal_sarpa(chart: dict) -> dict:
    longitudes = {name: chart["grahas"][name]["longitude"] for name in SEVEN}
    rahu = chart["grahas"]["Rahu"]
    ketu = chart["grahas"]["Ketu"]

    forward = _hemmed(longitudes, rahu["longitude"], ketu["longitude"])
    reverse = _hemmed(longitudes, ketu["longitude"], rahu["longitude"])
    present = forward or reverse
    name = KAAL_SARPA_TYPES[rahu["house"] - 1] if forward else None

    if not present:
        label = None
        description = "You do not have Kaal Sarp Yoga. "
    elif forward:
        label = KAAL_SARPA_LABEL
        description = (
            f"You have Kaal Sarpa Yoga because all the planets are between "
            f"Ketu and Rahu.  Since Rahu and Ketu is in {_ordinal(rahu['house'])} "
            f"and {_ordinal(ketu['house'])}, the type of Kaal Sarpa Yoga is {name}. "
        )
    else:
        label = KAAL_AMRITA_LABEL
        description = (
            "You have Kaal Amrita Yoga because all the planets are between "
            "Rahu and Ketu"
        )

    return {
        "type": name,
        "dosha_type": label,
        "has_dosha": present,
        "direction": "forward" if forward else "reverse" if reverse else None,
        "rahu_house": rahu["house"],
        "ketu_house": ketu["house"],
        "description": description,
    }


def papasamyam(chart: dict) -> dict:
    """The dosha grid from Lagna, Moon and Venus, and its weighted total."""
    signs = {name: chart["grahas"][name]["sign_index"] for name in chart["grahas"]}
    references = {
        "Ascendant": chart["lagna"]["sign_index"],
        "Moon": signs["Moon"],
        "Venus": signs["Venus"],
    }

    blocks = []
    for reference in PAPA_REFERENCES:
        base = references[reference]
        blocks.append({
            "name": reference,
            "planet_dosha": [
                {
                    "id": planet_id,
                    "name": planet,
                    "position": (signs[planet] - base) % 12 + 1,
                    "has_dosha": (signs[planet] - base) % 12 + 1 in PAPA_HOUSES,
                }
                for planet, planet_id in PAPA_PLANETS
            ],
        })
    total = sum(
        PAPA_REFERENCE_WEIGHT[block["name"]]
        for block in blocks
        for entry in block["planet_dosha"] if entry["has_dosha"]
    )
    return {"total_points": total, "papa_samyam": {"papa_planet": blocks}}


# Recovered by least squares over thirty-six charts: twelve unknowns, one
# equation each, worst residual 2.4e-10. The weight turns out to depend only
# on the reference point and not at all on which malefic sits there, which is
# why two sample totals were never going to pin it down -- but it does mean a
# dosha seen from the Lagna counts four times one seen from Venus.
PAPA_REFERENCE_WEIGHT = {"Ascendant": 1.0, "Moon": 0.5, "Venus": 0.25}
PAPA_POINTS_PARITY = "grid and total_points both verified"


def compute(chart: dict) -> dict:
    return {
        "kaal_sarpa": {**kaal_sarpa(chart), **provenance.KAAL_SARPA},
        "papasamyam": {**papasamyam(chart), "parity": PAPA_POINTS_PARITY,
                       **provenance.PAPASAMYAM},
    }
