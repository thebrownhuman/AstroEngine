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

Sarvashtakavarga is the column sum of the seven prastara rows. Its reduced
tables follow Prokerala's sarvashtakavarga endpoint, which reduces each graha
differently from its own ashtakavarga endpoint; see `sarva_reductions`.
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

# The same tables as the Sanskrit of Sharma's BPHS (V2 Ch.68 v46-63) reads
# them, used under strict_bphs. Four cells move; every row total stays.
BENEFIC_STRICT: dict[str, dict[str, tuple[int, ...]]] = {
    subject: dict(rows) for subject, rows in BENEFIC.items()
}
BENEFIC_STRICT["Moon"]["Moon"] = (1, 3, 6, 7, 9, 10, 11)          # v49-51
BENEFIC_STRICT["Moon"]["Mars"] = (2, 3, 5, 6, 10, 11)             # v49-51
BENEFIC_STRICT["Moon"]["Jupiter"] = (1, 2, 4, 7, 8, 10, 11)       # v49-51
BENEFIC_STRICT["Venus"]["Mars"] = (3, 4, 6, 9, 11, 12)            # v59-60
for _subject, _rows in BENEFIC_STRICT.items():
    assert sum(len(h) for h in _rows.values()) == EXPECTED_TOTALS[_subject],         f"{_subject}: strict row total"


def table(strict_bphs: bool = False) -> dict[str, dict[str, tuple[int, ...]]]:
    return BENEFIC_STRICT if strict_bphs else BENEFIC


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


def bhinna(subject: str, reference_signs: dict[str, int],
           strict_bphs: bool = False) -> list[int]:
    """Bindus for one graha, indexed by sign 0-11.

    `reference_signs` gives the sign index of each contributor, including
    "Lagna".
    """
    scores = [0] * 12
    for contributor, houses in table(strict_bphs)[subject].items():
        base = reference_signs[contributor]
        for house in houses:
            scores[(base + house - 1) % 12] += 1
    return scores


def contributions(subject: str, reference_signs: dict[str, int],
                  strict_bphs: bool = False) -> dict[str, list[int]]:
    """Same as `bhinna`, but kept split by contributor (the prastara grid)."""
    grid = {}
    for contributor, houses in table(strict_bphs)[subject].items():
        row = [0] * 12
        base = reference_signs[contributor]
        for house in houses:
            row[(base + house - 1) % 12] = 1
        grid[contributor] = row
    return grid


def trikona_shodhana(scores: list[int], strict_bphs: bool = False) -> list[int]:
    """Trinal reduction.

    Within each trine, a zero anywhere zeroes all three; otherwise the smallest
    value is subtracted from all three. Under strict_bphs a trine holding a
    zero is left as it is (Sharma V2 Ch.69 v4).
    """
    out = list(scores)
    for trine in TRINES:
        values = [scores[s] for s in trine]
        least = min(values)
        if least == 0 and strict_bphs:
            continue
        for sign in trine:
            out[sign] = 0 if least == 0 else scores[sign] - least
    return out


def ekadhipatya_shodhana(scores: list[int], occupied: set[int],
                         strict_bphs: bool = False) -> list[int]:
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
    ekaadhipatya in Mesha: 0 vs 4". strict_bphs zeroes it on a tie, as
    Sharma V2 Ch.70 v5 says.
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
            out[b] = 0 if second < first or (strict_bphs and second == first) else first
        else:
            out[a] = 0 if first < second or (strict_bphs and first == second) else second
    return out


def _trine_minimum_removed(scores: list[int]) -> list[int]:
    """Trinal reduction without the zero-in-a-trine rule."""
    out = list(scores)
    for trine in TRINES:
        least = min(scores[s] for s in trine)
        for sign in trine:
            out[sign] = scores[sign] - least
    return out


def sarva_reductions(grids: dict[str, list[int]],
                     occupied: set[int]) -> tuple[list[int], list[int]]:
    """Prokerala's reduced sarvashtakavarga, measured exact over seven births.

    Trikona sums each graha's trinal reduction *without* the zero rule; the
    per-graha endpoint does apply it. Ekaadhipatya sums each graha's same-lord
    reduction taken from the raw prastara, not the trikona table, and counts
    Rahu, Ketu and the lagna as occupants. Neither matches the textbook order.
    """
    trikona = [0] * 12
    ekadhipatya = [0] * 12
    for scores in grids.values():
        for sign, value in enumerate(_trine_minimum_removed(scores)):
            trikona[sign] += value
        for sign, value in enumerate(ekadhipatya_shodhana(scores, occupied)):
            ekadhipatya[sign] += value
    return trikona, ekadhipatya


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
    """Every ashtakavarga view for one chart, keyed by graha.

    Follows the chart's `engine.strict_bphs` stamp.
    """
    strict = bool(chart.get("engine", {}).get("strict_bphs"))
    signs = reference_signs(chart)
    lagna_sign = signs["Lagna"]
    occupied = {chart["grahas"][name]["sign_index"] for name in SUBJECTS}

    tables = {}
    reduced = {}
    for subject in SUBJECTS:
        grid = contributions(subject, signs, strict)
        scores = [sum(row[s] for row in grid.values()) for s in range(12)]
        trikona = trikona_shodhana(scores, strict)
        ekadhipatya = ekadhipatya_shodhana(trikona, occupied, strict)
        reduced[subject] = (trikona, ekadhipatya)
        tables[subject] = {
            "total": sum(scores),
            "by_sign": scores,
            "prastara": {"houses": _as_houses(scores, lagna_sign, grid),
                         "score": sum(scores)},
            "trikona": {"houses": _as_houses(trikona, lagna_sign),
                        "score": sum(trikona)},
            "ekaadhipatya": {"houses": _as_houses(ekadhipatya, lagna_sign),
                             "score": sum(ekadhipatya),
                             **(provenance.EKADHIPATYA_STRICT if strict
                                else provenance.EKADHIPATYA)},
        }

    sarva = [sum(tables[s]["by_sign"][i] for s in SUBJECTS) for i in range(12)]
    sarva_grid = {s: tables[s]["by_sign"] for s in SUBJECTS}
    sarva_occupied = {g["sign_index"] for g in chart["grahas"].values()} | {lagna_sign}
    if strict:
        # The textbook order: each graha reduced on its own, then summed.
        sarva_trikona = [sum(reduced[s][0][i] for s in SUBJECTS) for i in range(12)]
        sarva_ekadhipatya = [sum(reduced[s][1][i] for s in SUBJECTS) for i in range(12)]
        tables_source, sarva_source = provenance.ASHTAKAVARGA_STRICT, provenance.SARVA_STRICT
    else:
        sarva_trikona, sarva_ekadhipatya = sarva_reductions(sarva_grid, sarva_occupied)
        tables_source, sarva_source = provenance.ASHTAKAVARGA, provenance.SARVA_REDUCTIONS
    return {
        "ashtakavarga": tables,
        # Sibling, not merged: `ashtakavarga` is keyed by graha name and a
        # consumer iterating it must not find "source" among the grahas.
        "ashtakavarga_source": tables_source,
        "sarvashtakavarga": {
            "by_sign": sarva,
            "total": sum(sarva),
            # The column sum of the seven prastara rows, so it inherits the
            # bindu tables' authority and none of the reduction's.
            **tables_source,
            "prastara": {"houses": _as_houses(sarva, lagna_sign, sarva_grid),
                         "score": sum(sarva)},
            "trikona": {"houses": _as_houses(sarva_trikona, lagna_sign),
                        "score": sum(sarva_trikona), **sarva_source},
            "ekaadhipatya": {"houses": _as_houses(sarva_ekadhipatya, lagna_sign),
                             "score": sum(sarva_ekadhipatya),
                             **sarva_source},
        },
    }
