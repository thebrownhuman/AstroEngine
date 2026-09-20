"""Porutham: the South Indian nakshatra compatibility checks.

Where Ashtakoot scores out of thirty-six, this is a list of yes/no tests. Ten
of them make up the common list, and Prokerala's thirumana variant adds Nadi
and Varna for twelve. All twelve depend only on the two nakshatras and their
padas -- no birth time, no place.

    1 Dina    2 Gana    3 Mahendra   4 Stree Deergha
    5 Yoni    6 Veda    7 Rajju      8 Rasi
    9 Rasi Lord   10 Vashya   11 Nadi   12 Varna

The rasi a nakshatra falls in is fixed (each sign spans two and a quarter
nakshatras), so Rasi, Rasi Lord, Vashya and Varna can all be derived from the
nakshatra and pada alone.

Parity, stated plainly. All twelve reproduce Prokerala exactly, over every
one of the 729 star pairs and all 954 measured pada combinations.

Six needed correcting off the measurement rather than off the textbooks.
Stree Deergha starts at nine rather than thirteen. Yoni fails only on
permanent enmity. Veda folds Chitra into the Mrigashirsha-Dhanishta pair
instead of leaving it unpaired. Gana is its own three-cell table, not the koot
behind a threshold. Rajju is not the five body bands at all -- only every
third star can clash, and only inside its own band. Nadi is not even a
partition: Mula belongs to no band and Purva Ashadha to two.

The last four -- Rasi, Rasi Lord, Vashya, Varna -- held out longest and turned
out to share one cause. They are sign rules, but not on the sign this engine
computes: **Prokerala counts the pada from one where it should count from
zero**, so the sign it uses for a nakshatra pada is one pada further along.
That is the same off-by-one that makes pada 4 spill into the next nakshatra.

On our sign they look like nothing -- not sign rules, not count rules, and
apparently pada-sensitive in a way no modulus explained. On theirs all four
are exact functions of the sign pair, covering all 144 cells with no
contradiction anywhere. Varna is then simply the ordinary varna rank and Rasi
Lord rejects exactly three mutual-enemy lord pairs; Rasi and Vashya are
carried as measured 12x12 tables because their classical forms get only 100
and 42 of 144 cells respectively.

One thing to know before calling the API itself: **pada 4 is broken on
Prokerala's side.** Sending `girl_nakshatra_pada=4` or `boy_nakshatra_pada=4`
makes every *star*-based check behave as though that person were in the first
pada of the next nakshatra. Pada 0 is rejected outright, so this is not a
zero-based convention, it is the same off-by-one seen from the other end. The
engine reproduces their sign, which is observable and consistent, but not the
pada-4 star shift, which is not; validation sweeps avoid pada 4 instead.
"""

from __future__ import annotations

from .constants import NAKSHATRAS, SIGN_LORDS
from .matching import (
    GANA_BY_NAKSHATRA, NADI_BY_NAKSHATRA, VARNA_BY_SIGN, VARNA_RANK,
    YONI_BY_NAKSHATRA, YONI_POINTS,
)

NAKSHATRA_COUNT = 27
PADAS_PER_NAKSHATRA = 4
PADAS_PER_SIGN = 9


def rasi_of(nakshatra: int, pada: int) -> int:
    """Sign holding a given nakshatra pada. Nine padas make one sign."""
    return ((nakshatra * PADAS_PER_NAKSHATRA) + (pada - 1)) // PADAS_PER_SIGN % 12


def degree_of(nakshatra: int, pada: int) -> float:
    """Mid-pada longitude, enough to place the half-sign vasya splits."""
    arc = 360.0 / (NAKSHATRA_COUNT * PADAS_PER_NAKSHATRA)
    return ((nakshatra * PADAS_PER_NAKSHATRA + pada - 1) * arc + arc / 2) % 30.0


def count_from(first: int, second: int) -> int:
    """1-27 position of the second nakshatra counted from the first."""
    return (second - first) % NAKSHATRA_COUNT + 1


# --- 1 dina -------------------------------------------------------------------

# Counting from the bride's star to the groom's and dividing by nine, these
# remainders are the favourable ones.
DINA_GOOD_REMAINDERS = frozenset({2, 4, 6, 8, 0})


def dina(boy: int, girl: int) -> bool:
    return count_from(girl, boy) % 9 in DINA_GOOD_REMAINDERS


# --- 2 gana -------------------------------------------------------------------

# Not the ashtakoot gana koot behind a threshold, which is what it looks like
# from a single bride. Over 213 measured pairs only three of the nine cells
# fail, and one of them -- a Rakshasa groom with a Manushya bride -- passes
# here while scoring zero in the koot. So the porutham carries its own table.
GANA_PORUTHAM_FAILS = frozenset({
    ("Devata", "Rakshasa"),
    ("Manushya", "Rakshasa"),
    ("Rakshasa", "Devata"),
})


def gana(boy: int, girl: int) -> bool:
    return (GANA_BY_NAKSHATRA[boy], GANA_BY_NAKSHATRA[girl])         not in GANA_PORUTHAM_FAILS


# --- 3 mahendra ---------------------------------------------------------------

MAHENDRA_COUNTS = frozenset({4, 7, 10, 13, 16, 19, 22, 25})


def mahendra(boy: int, girl: int) -> bool:
    return count_from(girl, boy) in MAHENDRA_COUNTS


# --- 4 stree deergha ----------------------------------------------------------

# Measured: counts one through eight fail, nine and up pass. Sources that put
# the threshold at thirteen do not match Prokerala.
STREE_DEERGHA_MINIMUM = 9


def stree_deergha(boy: int, girl: int) -> bool:
    return count_from(girl, boy) >= STREE_DEERGHA_MINIMUM


# --- 5 yoni -------------------------------------------------------------------

# Only the seven permanent enmities fail. Ordinary enmity, which costs a point
# in the ashtakoot yoni koot, still passes the porutham.
YONI_FAIL_POINTS = 0.0


def yoni(boy: int, girl: int) -> bool:
    boy_animal = YONI_BY_NAKSHATRA[boy][0]
    girl_animal = YONI_BY_NAKSHATRA[girl][0]
    if boy_animal == girl_animal:
        return True
    return YONI_POINTS.get((boy_animal, girl_animal), 2.0) != YONI_FAIL_POINTS


# --- 6 veda -------------------------------------------------------------------

# Twelve opposed pairs and one triple. Every source prints thirteen pairs and
# leaves Chitra unpaired; Prokerala instead folds Chitra into the
# Mrigashirsha-Dhanishta pair, so those three are all opposed to each other.
VEDA_GROUPS = [
    (0, 17), (1, 16), (2, 15), (3, 14), (5, 21), (6, 20), (7, 19),
    (8, 18), (9, 26), (10, 25), (11, 24), (12, 23),
    (4, 13, 22),
]
VEDA = {}
for _group in VEDA_GROUPS:
    for _member in _group:
        VEDA[_member] = frozenset(_group) - {_member}


def veda(boy: int, girl: int) -> bool:
    return girl not in VEDA.get(boy, frozenset())


# --- 7 rajju ------------------------------------------------------------------

# The textbook rajju walks the twenty-seven stars up and down the body in five
# bands and fails whenever the couple share one. Prokerala does something much
# narrower, and the shape is unmistakable once every star is paired with
# itself: only the nine stars at positions 1, 4, 7 ... -- every third one --
# can clash at all, and the other eighteen pass even against themselves.
#
# Those nine split into two bands six apart, and the check fails only inside a
# band: {1, 7, 13, 19, 25} and {4, 10, 16, 22}. Measured with a full diagonal
# and six complete bride rows, 223 pairs, no exceptions.
RAJJU_STEP = 3
RAJJU_BAND = 6
RAJJU_OFFSET = 1

RAJJU_BANDS = {
    residue: sorted(n for n in range(NAKSHATRA_COUNT)
                    if n % RAJJU_STEP == RAJJU_OFFSET and n % RAJJU_BAND == residue)
    for residue in (1, 4)
}
RAJJU_BY_NAKSHATRA = {
    n: residue for residue, members in RAJJU_BANDS.items() for n in members
}
assert RAJJU_BANDS[1] == [1, 7, 13, 19, 25]
assert RAJJU_BANDS[4] == [4, 10, 16, 22]


def rajju(boy: int, girl: int) -> bool:
    band = RAJJU_BY_NAKSHATRA.get(boy)
    return band is None or band != RAJJU_BY_NAKSHATRA.get(girl)


# --- 8 rasi -------------------------------------------------------------------

# The four checks below are sign rules after all, but not on the sign this
# engine computes. Prokerala counts the pada from one where it should count
# from zero, so its sign for a nakshatra pada is one pada further along -- the
# same off-by-one that makes pada 4 spill into the next nakshatra. On their
# sign all four become exact functions of the sign pair, covering all 144
# cells with no contradiction across 954 measured pairs; on ours they look
# like nothing at all, which is what cost so much time.
PROKERALA_PADA_OFFSET = 1


def prokerala_rasi_of(nakshatra: int, pada: int) -> int:
    """The sign Prokerala uses for these four checks, off-by-one included."""
    return ((nakshatra * PADAS_PER_NAKSHATRA + pada - 1 + PROKERALA_PADA_OFFSET)
            // PADAS_PER_SIGN) % 12


# Measured. Not count-based: the 2nd, 3rd, 4th, 5th, 6th and 8th positions are
# each good for some sign pairs and bad for others, so the classical "reject
# the 2nd and the 12th" reproduces only 100 of the 144 cells.
RASI_TABLE = (
    "111111111111",
    "111111111111",
    "111111111111",
    "111111111111",
    "111111111111",
    "011111111111",
    "101111111111",
    "010111111111",
    "001011111111",
    "000101111111",
    "000010111111",
    "000001011111",
)


def rasi(boy_sign: int, girl_sign: int) -> bool:
    return RASI_TABLE[girl_sign][boy_sign] == "1"


# --- 9 rasi lord --------------------------------------------------------------

# A function of the two sign lords, and only three unordered pairs fail. They
# are mutual enemies in the classical table, but the classical rule rejects
# far more pairs than this and manages only 104 of 144 cells.
RASI_LORD_ENEMIES = frozenset({
    frozenset({"Sun", "Saturn"}),
    frozenset({"Sun", "Venus"}),
    frozenset({"Moon", "Mercury"}),
})


def rasi_lord(boy_sign: int, girl_sign: int) -> bool:
    pair = frozenset({SIGN_LORDS[boy_sign], SIGN_LORDS[girl_sign]})
    return pair not in RASI_LORD_ENEMIES


# --- 10 vashya ----------------------------------------------------------------

# Measured, and symmetric in bride and groom. The ashtakoot vasya groups get
# only 42 of the 144 cells, so this is a different table wearing the same name.
VASHYA_TABLE = (
    "000010010110",
    "000100100000",
    "000001000000",
    "010000011000",
    "100000100000",
    "001000100001",
    "010011000100",
    "100100000000",
    "000100000001",
    "100000100011",
    "100000000100",
    "000001001100",
)


def vashya(boy_sign: int, girl_sign: int) -> bool:
    return VASHYA_TABLE[girl_sign][boy_sign] == "1"


# --- 11 nadi, 12 varna --------------------------------------------------------

# Prokerala's nadi bands are the koot's three, with one entry misplaced in a
# way that makes them stop being a partition. Read straight off four complete
# bride rows:
#
#     Adi     0  5  6 11 12 17 19 23 24
#     Madhya  1  4  7 10 13 16 19 22 25
#     Antya   2  3  8  9 14 15 20 21 26
#
# Purva Ashadha is in two bands and Mula is in none, so Mula clashes with
# nobody and Purva Ashadha clashes with two thirds of the zodiac. That is the
# same off-by-one family as the pada-four bug: one slot in their table holds
# its neighbour's value. Membership is therefore a set, and the check passes
# when the two sets do not meet.
NADI_UNBANDED = 18
NADI_DOUBLE_BANDED = 19

NADI_PORUTHAM_BANDS = {
    n: (frozenset() if n == NADI_UNBANDED
        else frozenset({"Adi", "Madhya"}) if n == NADI_DOUBLE_BANDED
        else frozenset({NADI_BY_NAKSHATRA[n]}))
    for n in range(NAKSHATRA_COUNT)
}


def nadi(boy: int, girl: int) -> bool:
    return not (NADI_PORUTHAM_BANDS[boy] & NADI_PORUTHAM_BANDS[girl])


# The ordinary varna rank -- Brahmana, Kshatriya, Vaishya, Shudra by sign --
# with the groom's not allowed to fall below the bride's. On Prokerala's sign
# it reproduces all 144 cells exactly. The modulo-nine reading found earlier
# was this same rule seen through the off-by-one, which is why it worked at
# pada 1 and nowhere else.

def varna(boy_sign: int, girl_sign: int) -> bool:
    return VARNA_RANK[VARNA_BY_SIGN[boy_sign]] >= VARNA_RANK[VARNA_BY_SIGN[girl_sign]]


# --- assembly -----------------------------------------------------------------

TEN = [
    (1, "Dina Porutham"), (2, "Gana Porutham"), (3, "Mahendra Porutham"),
    (4, "Stree Deergha Porutham"), (5, "Yoni Porutham"), (6, "Veda Porutham"),
    (7, "Rajju Porutham"), (8, "Rasi Porutham"), (9, "Rasi Lord Porutham"),
    (10, "Vashya Porutham"),
]
TWELVE = TEN + [(11, "Nadi Porutham"), (12, "Varna Porutham")]

VERIFIED = frozenset(range(1, 13))
PARITY = {key: ("verified" if key in VERIFIED else "unverified")
          for key, _ in TWELVE}


def compute(
    boy_nakshatra: int, boy_pada: int, girl_nakshatra: int, girl_pada: int,
    twelve: bool = False,
) -> dict:
    """The porutham checklist for one nakshatra pair."""
    boy_sign = rasi_of(boy_nakshatra, boy_pada)
    girl_sign = rasi_of(girl_nakshatra, girl_pada)
    # Rasi, Rasi Lord, Vashya and Varna run on Prokerala's off-by-one sign.
    boy_their_sign = prokerala_rasi_of(boy_nakshatra, boy_pada)
    girl_their_sign = prokerala_rasi_of(girl_nakshatra, girl_pada)

    verdicts = {
        1: dina(boy_nakshatra, girl_nakshatra),
        2: gana(boy_nakshatra, girl_nakshatra),
        3: mahendra(boy_nakshatra, girl_nakshatra),
        4: stree_deergha(boy_nakshatra, girl_nakshatra),
        5: yoni(boy_nakshatra, girl_nakshatra),
        6: veda(boy_nakshatra, girl_nakshatra),
        7: rajju(boy_nakshatra, girl_nakshatra),
        8: rasi(boy_their_sign, girl_their_sign),
        9: rasi_lord(boy_their_sign, girl_their_sign),
        10: vashya(boy_their_sign, girl_their_sign),
        11: nadi(boy_nakshatra, girl_nakshatra),
        12: varna(boy_their_sign, girl_their_sign),
    }

    checks = TWELVE if twelve else TEN
    matches = [{"id": key, "name": name, "has_porutham": verdicts[key],
                "parity": PARITY[key]}
               for key, name in checks]
    obtained = sum(entry["has_porutham"] for entry in matches)
    verified = [entry for entry in matches if entry["parity"] == "verified"]
    return {
        "maximum_points": len(checks),
        "obtained_points": obtained,
        "verified_points": sum(entry["has_porutham"] for entry in verified),
        "verified_maximum": len(verified),
        "matches": matches,
        "boy": {"nakshatra": NAKSHATRAS[boy_nakshatra], "pada": boy_pada,
                "rasi_index": boy_sign},
        "girl": {"nakshatra": NAKSHATRAS[girl_nakshatra], "pada": girl_pada,
                 "rasi_index": girl_sign},
    }
