"""Ashtakavarga: the bindu (benefic point) tables of BPHS chapter 66.

Each of the seven grahas earns a bindu in a sign depending on where that sign
falls, counted from each of eight reference points -- the seven grahas and the
Lagna. The contribution tables below are the classical ones; the row totals
(48, 49, 39, 54, 56, 52, 39) and their sum (337) are asserted at import time,
which catches a mistyped digit immediately.

Three views are produced, matching what Prokerala returns:

  prastara      the raw bindu table
  trikona       after trikona shodhana (trinal reduction)
  ekaadhipatya  after ekadhipatya shodhana (same-lord reduction)

Sarvashtakavarga is the column sum of the seven prastara rows.
"""

from __future__ import annotations

from . import provenance
from .constants import SIGNS, SIGNS_EN, SIGN_LORDS

# Order matters: this is the order the classical tables are written in.
CONTRIBUTORS = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Lagna")
SUBJECTS = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")

# BENEFIC[subject][contributor] = houses, counted from the contributor's sign,
# in which the subject earns a bindu.
BENEFIC: dict[str, dict[str, tuple[int, ...]]] = {
    "Sun": {
        "Sun":     (1, 2, 4, 7, 8, 9, 10, 11),
        "Moon":    (3, 6, 10, 11),
        "Mars":    (1, 2, 4, 7, 8, 9, 10, 11),
        "Mercury": (3, 5, 6, 9, 10, 11, 12),
        "Jupiter": (5, 6, 9, 11),
        "Venus":   (6, 7, 12),
        "Saturn":  (1, 2, 4, 7, 8, 9, 10, 11),
        "Lagna":   (3, 4, 6, 10, 11, 12),
    },
    "Moon": {
        "Sun":     (3, 6, 7, 8, 10, 11),
        "Moon":    (1, 3, 6, 7, 10, 11),
        "Mars":    (2, 3, 5, 6, 9, 10, 11),
        "Mercury": (1, 3, 4, 5, 7, 8, 10, 11),
        "Jupiter": (1, 4, 7, 8, 10, 11, 12),
        "Venus":   (3, 4, 5, 7, 9, 10, 11),
        "Saturn":  (3, 5, 6, 11),
        "Lagna":   (3, 6, 10, 11),
    },
    "Mars": {
        "Sun":     (3, 5, 6, 10, 11),
        "Moon":    (3, 6, 11),
        "Mars":    (1, 2, 4, 7, 8, 10, 11),
        "Mercury": (3, 5, 6, 11),
        "Jupiter": (6, 10, 11, 12),
        "Venus":   (6, 8, 11, 12),
        "Saturn":  (1, 4, 7, 8, 9, 10, 11),
        "Lagna":   (1, 3, 6, 10, 11),
    },
    "Mercury": {
        "Sun":     (5, 6, 9, 11, 12),
        "Moon":    (2, 4, 6, 8, 10, 11),
        "Mars":    (1, 2, 4, 7, 8, 9, 10, 11),
        "Mercury": (1, 3, 5, 6, 9, 10, 11, 12),
        "Jupiter": (6, 8, 11, 12),
        "Venus":   (1, 2, 3, 4, 5, 8, 9, 11),
        "Saturn":  (1, 2, 4, 7, 8, 9, 10, 11),
        "Lagna":   (1, 2, 4, 6, 8, 10, 11),
    },
    "Jupiter": {
        "Sun":     (1, 2, 3, 4, 7, 8, 9, 10, 11),
        "Moon":    (2, 5, 7, 9, 11),
        "Mars":    (1, 2, 4, 7, 8, 10, 11),
        "Mercury": (1, 2, 4, 5, 6, 9, 10, 11),
        "Jupiter": (1, 2, 3, 4, 7, 8, 10, 11),
        "Venus":   (2, 5, 6, 9, 10, 11),
        "Saturn":  (3, 5, 6, 12),
        "Lagna":   (1, 2, 4, 5, 6, 7, 9, 10, 11),
    },
    "Venus": {
        "Sun":     (8, 11, 12),
        "Moon":    (1, 2, 3, 4, 5, 8, 9, 11, 12),
        "Mars":    (3, 5, 6, 9, 11, 12),
        "Mercury": (3, 5, 6, 9, 11),
        "Jupiter": (5, 8, 9, 10, 11),
        "Venus":   (1, 2, 3, 4, 5, 8, 9, 10, 11),
        "Saturn":  (3, 4, 5, 8, 9, 10, 11),
        "Lagna":   (1, 2, 3, 4, 5, 8, 9, 11),
    },
    "Saturn": {
        "Sun":     (1, 2, 4, 7, 8, 10, 11),
        "Moon":    (3, 6, 11),
        "Mars":    (3, 5, 6, 10, 11, 12),
        "Mercury": (6, 8, 9, 10, 11, 12),
        "Jupiter": (5, 6, 11, 12),
        "Venus":   (6, 11, 12),
        "Saturn":  (3, 5, 6, 11),
        "Lagna":   (1, 3, 4, 6, 10, 11),
    },
}

# Classical row totals. A transcription slip in the tables above changes one of
# these, so they are checked rather than trusted.
EXPECTED_TOTALS = {
    "Sun": 48, "Moon": 49, "Mars": 39, "Mercury": 54,
    "Jupiter": 56, "Venus": 52, "Saturn": 39,
}
SARVA_TOTAL = 337

for _subject, _rows in BENEFIC.items():
    assert tuple(_rows) == CONTRIBUTORS, f"{_subject}: contributor order"
    for _who, _houses in _rows.items():
        assert _houses == tuple(sorted(set(_houses))), f"{_subject}/{_who}: not a sorted set"
        assert all(1 <= h <= 12 for h in _houses), f"{_subject}/{_who}: house out of range"
    assert sum(len(h) for h in _rows.values()) == EXPECTED_TOTALS[_subject], \
        f"{_subject}: row total"
assert sum(EXPECTED_TOTALS.values()) == SARVA_TOTAL

# Trines of signs, used by trikona shodhana.
TRINES = [(0, 4, 8), (1, 5, 9), (2, 6, 10), (3, 7, 11)]

# Signs sharing a lord. The luminaries own one sign each and are exempt.
SAME_LORD_PAIRS = [(0, 7), (1, 6), (2, 5), (8, 11), (9, 10)]

HOUSE_NAMES = [
    "Tanu", "Dhan", "Sahaj", "Bandhu", "Putra", "Ari",
    "Yuvati", "Randhra", "Dharma", "Karma", "Labha", "Vyaya",
]

VEDIC_NAMES = {
    "Sun": "Ravi", "Moon": "Chandra", "Mercury": "Budha", "Venus": "Shukra",
    "Mars": "Kuja", "Jupiter": "Guru", "Saturn": "Shani", "Lagna": "Lagna",
}

# Prokerala's planet ids, which are not the order the tables are written in.
PLANET_IDS = {
    "Sun": 0, "Moon": 1, "Mercury": 2, "Venus": 3,
    "Mars": 4, "Jupiter": 5, "Saturn": 6, "Lagna": 100,
}
# The order Prokerala lists contributors inside a house.
RESPONSE_ORDER = ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Lagna")


def bhinna(subject: str, reference_signs: dict[str, int]) -> list[int]:
    """Bindus for one graha, indexed by sign 0-11.

    `reference_signs` gives the sign index of each contributor, including
    "Lagna".
    """
    scores = [0] * 12
    for contributor, houses in BENEFIC[subject].items():
        base = reference_signs[contributor]
        for house in houses:
            scores[(base + house - 1) % 12] += 1
    return scores


def contributions(subject: str, reference_signs: dict[str, int]) -> dict[str, list[int]]:
    """Same as `bhinna`, but kept split by contributor (the prastara grid)."""
    grid = {}
    for contributor, houses in BENEFIC[subject].items():
        row = [0] * 12
        base = reference_signs[contributor]
        for house in houses:
            row[(base + house - 1) % 12] = 1
        grid[contributor] = row
    return grid


def trikona_shodhana(scores: list[int]) -> list[int]:
    """Trinal reduction.

    Within each trine, a zero anywhere zeroes all three; otherwise the smallest
    value is subtracted from all three.
    """
    out = list(scores)
    for trine in TRINES:
        values = [scores[s] for s in trine]
        least = min(values)
        for sign in trine:
            out[sign] = 0 if least == 0 else scores[sign] - least
    return out


def ekadhipatya_shodhana(scores: list[int], occupied: set[int]) -> list[int]:
    """Same-lord reduction, applied to the trikona-reduced table.

    For the five grahas that own two signs:

      * both signs occupied      -> untouched
      * either sign already zero -> untouched
      * both signs empty         -> both take the lesser value, and both become
                                    zero when the values are equal
      * one occupied, one empty  -> the empty sign is levelled down to the
                                    occupied one, but zeroed outright if it
                                    already held strictly less

    That last clause is the one the texts state loosely, and getting it wrong
    is visible: leaving a smaller empty sign alone shows up as "Mars
    ekaadhipatya in Kanya: 1 vs 0", and zeroing it on a tie as "Saturn
    ekaadhipatya in Mesha: 0 vs 4".
    """
    out = list(scores)
    for a, b in SAME_LORD_PAIRS:
        first, second = out[a], out[b]
        if first == 0 or second == 0:
            continue
        a_full, b_full = a in occupied, b in occupied
        if a_full and b_full:
            continue
        if not a_full and not b_full:
            out[a] = out[b] = 0 if first == second else min(first, second)
        elif a_full:
            out[b] = first if second >= first else 0
        else:
            out[a] = second if first >= second else 0
    return out


def _house_block(house_number: int, sign: int) -> dict:
    return {
        "house": {"id": house_number - 1, "name": HOUSE_NAMES[house_number - 1],
                  "number": house_number},
        "rasi": {"index": sign, "name": SIGNS[sign], "name_en": SIGNS_EN[sign],
                 "lord": SIGN_LORDS[sign]},
    }


def _as_houses(scores: list[int], lagna_sign: int,
               grid: dict[str, list[int]] | None = None) -> list[dict]:
    houses = []
    for number in range(1, 13):
        sign = (lagna_sign + number - 1) % 12
        block = _house_block(number, sign)
        if grid is not None:
            block["planets"] = [
                {"planet": {"id": PLANET_IDS[who], "name": who,
                            "vedic_name": VEDIC_NAMES[who]},
                 "score": grid[who][sign]}
                for who in RESPONSE_ORDER if who in grid
            ]
        block["score"] = scores[sign]
        houses.append(block)
    return houses


def reference_signs(chart: dict) -> dict[str, int]:
    signs = {name: chart["grahas"][name]["sign_index"] for name in SUBJECTS}
    signs["Lagna"] = chart["lagna"]["sign_index"]
    return signs


def compute(chart: dict) -> dict:
    """Every ashtakavarga view for one chart, keyed by graha."""
    signs = reference_signs(chart)
    lagna_sign = signs["Lagna"]
    occupied = {chart["grahas"][name]["sign_index"] for name in SUBJECTS}

    tables = {}
    for subject in SUBJECTS:
        grid = contributions(subject, signs)
        scores = [sum(row[s] for row in grid.values()) for s in range(12)]
        trikona = trikona_shodhana(scores)
        ekadhipatya = ekadhipatya_shodhana(trikona, occupied)
        tables[subject] = {
            "total": sum(scores),
            "by_sign": scores,
            "prastara": {"houses": _as_houses(scores, lagna_sign, grid),
                         "score": sum(scores)},
            "trikona": {"houses": _as_houses(trikona, lagna_sign),
                        "score": sum(trikona)},
            "ekaadhipatya": {"houses": _as_houses(ekadhipatya, lagna_sign),
                             "score": sum(ekadhipatya),
                             **provenance.EKADHIPATYA},
        }

    sarva = [sum(tables[s]["by_sign"][i] for s in SUBJECTS) for i in range(12)]
    sarva_grid = {s: tables[s]["by_sign"] for s in SUBJECTS}
    return {
        "ashtakavarga": tables,
        # Sibling, not merged: `ashtakavarga` is keyed by graha name and a
        # consumer iterating it must not find "source" among the grahas.
        "ashtakavarga_source": provenance.ASHTAKAVARGA,
        "sarvashtakavarga": {
            "by_sign": sarva,
            "total": sum(sarva),
            "prastara": {"houses": _as_houses(sarva, lagna_sign, sarva_grid),
                         "score": sum(sarva)},
        },
    }
