"""Ashtakoot guna milan: the thirty-six point compatibility score.

Eight koots, weighted one through eight, all read off the two Moons -- their
sign for Varna, Vasya, Graha Maitri and Bhakoot, their nakshatra for Tara,
Yoni, Gana and Nadi. Nothing here needs a birth time beyond what fixes the
Moon, which is why the endpoint takes only dates and places.

    Varna 1   Vasya 2   Tara 3   Yoni 4
    Graha Maitri 5   Gana 6   Bhakoot 7   Nadi 8

Two of the eight carry veto weight in practice: identical Nadi ("Nadi dosha")
costs all eight points, and a 6/8 or 2/12 sign relationship ("Bhakoot dosha")
costs all seven.

The classification tables -- which sign is which Varna, which nakshatra is
which Yoni -- are classical and agreed. The scoring matrices are where sources
differ, and six cells of the published ones turned out to be wrong for
Prokerala: three in Vasya, two in Gana, and two yoni pairs that are friends
and enemies rather than neutral. All were found by comparing per-koot points
on twenty-two pairs; see validation/verify_matching.py.

Coverage, stated plainly: 22 pairs exercise 17 of the 25 Vasya cells, all 9
Gana cells, and 22 of the 105 unordered Yoni pairs. Every cell reached agrees
exactly. The rest are the published values, unverified.
"""

from __future__ import annotations

from . import provenance
from .constants import (
    NAKSHATRAS, PROKERALA_NAKSHATRA_NAMES, SIGNS, SIGNS_EN, SIGN_LORDS,
)
from .relationships import ENEMY, FRIEND, natural

MAXIMUM_POINTS = 36

# --- varna (1 point) ----------------------------------------------------------

VARNA_BY_SIGN = [
    "Kshatriya", "Vaishya", "Shudra", "Brahmin",
    "Kshatriya", "Vaishya", "Shudra", "Brahmin",
    "Kshatriya", "Vaishya", "Shudra", "Brahmin",
]
VARNA_RANK = {"Shudra": 1, "Vaishya": 2, "Kshatriya": 3, "Brahmin": 4}


def varna(boy_sign: int, girl_sign: int) -> tuple[str, str, float]:
    boy, girl = VARNA_BY_SIGN[boy_sign], VARNA_BY_SIGN[girl_sign]
    # The groom's varna may equal or exceed the bride's, not fall below it.
    return boy, girl, 1.0 if VARNA_RANK[boy] >= VARNA_RANK[girl] else 0.0


# --- vasya (2 points) ---------------------------------------------------------

# Sagittarius and Capricorn are split at 15 degrees, so vasya needs the degree
# in the sign, not just the sign.
VASYA_BY_SIGN = [
    "Chatushpada", "Chatushpada", "Manava", "Jalachara",
    "Vanachara", "Manava", "Manava", "Keeta",
    None, None, "Manava", "Jalachara",
]
VASYA_GROUPS = ("Chatushpada", "Manava", "Jalachara", "Vanachara", "Keeta")

# Rows are the groom's group, columns the bride's.
VASYA_POINTS = {
    "Chatushpada": {"Chatushpada": 2.0, "Manava": 1.0, "Jalachara": 1.0,
                    "Vanachara": 0.0, "Keeta": 1.0},
    "Manava":      {"Chatushpada": 1.0, "Manava": 2.0, "Jalachara": 0.5,
                    "Vanachara": 0.0, "Keeta": 0.0},
    "Jalachara":   {"Chatushpada": 1.0, "Manava": 0.5, "Jalachara": 2.0,
                    "Vanachara": 1.0, "Keeta": 1.0},
    "Vanachara":   {"Chatushpada": 0.0, "Manava": 0.0, "Jalachara": 1.0,
                    "Vanachara": 2.0, "Keeta": 1.0},
    "Keeta":       {"Chatushpada": 1.0, "Manava": 1.0, "Jalachara": 0.5,
                    "Vanachara": 1.0, "Keeta": 2.0},
}


def vasya_group(sign: int, degree_in_sign: float) -> str:
    fixed = VASYA_BY_SIGN[sign]
    if fixed is not None:
        return fixed
    if sign == 8:       # Sagittarius: human first half, quadruped second
        return "Manava" if degree_in_sign < 15.0 else "Chatushpada"
    return "Chatushpada" if degree_in_sign < 15.0 else "Jalachara"   # Capricorn


def vasya(boy: tuple[int, float], girl: tuple[int, float]) -> tuple[str, str, float]:
    boy_group = vasya_group(*boy)
    girl_group = vasya_group(*girl)
    return boy_group, girl_group, VASYA_POINTS[boy_group][girl_group]


# --- tara (3 points) ----------------------------------------------------------

TARA_NAMES = ["Janma", "Sampat", "Vipat", "Kshema", "Pratyari",
              "Sadhaka", "Vadha", "Mitra", "Ati Mitra"]
# Vipat, Pratyari and Vadha are the hostile taras.
HOSTILE_TARAS = frozenset({3, 5, 7})


def tara_count(from_nakshatra: int, to_nakshatra: int) -> int:
    """1-9 position of one nakshatra counted from the other."""
    return (to_nakshatra - from_nakshatra) % 27 % 9 + 1


def tara(boy_nakshatra: int, girl_nakshatra: int) -> tuple[str, str, float]:
    """Both directions are counted; each hostile one costs its half.

    The label Prokerala prints against this koot is not the tara name but the
    person's own nakshatra, so that is what is returned here. `tara_names`
    gives the actual taras.
    """
    forward = tara_count(girl_nakshatra, boy_nakshatra)
    backward = tara_count(boy_nakshatra, girl_nakshatra)
    score = sum(0.0 if count in HOSTILE_TARAS else 1.5
                for count in (forward, backward))
    return (PROKERALA_NAKSHATRA_NAMES[boy_nakshatra],
            PROKERALA_NAKSHATRA_NAMES[girl_nakshatra], score)


def tara_names(boy_nakshatra: int, girl_nakshatra: int) -> tuple[str, str]:
    """The taras themselves: boy counted from girl, and the reverse."""
    return (TARA_NAMES[tara_count(girl_nakshatra, boy_nakshatra) - 1],
            TARA_NAMES[tara_count(boy_nakshatra, girl_nakshatra) - 1])


# --- yoni (4 points) ----------------------------------------------------------

YONI_ANIMALS = ["Horse", "Elephant", "Sheep", "Serpent", "Dog", "Cat", "Rat",
                "Cow", "Buffalo", "Tiger", "Deer", "Monkey", "Mongoose", "Lion"]
# Prokerala reports the yoni under its Sanskrit name, in these spellings.
YONI_SANSKRIT = {
    "Horse": "Ashwa", "Elephant": "Gaja", "Sheep": "Mesha", "Serpent": "Sarpa",
    "Dog": "Swah", "Cat": "Marjarah", "Rat": "Mushika", "Cow": "Gau",
    "Buffalo": "Mahisha", "Tiger": "Vyagrah", "Deer": "Mriga",
    "Monkey": "Vanara", "Mongoose": "Nakula", "Lion": "Singha",
}

# Nakshatra -> (animal, male?)
YONI_BY_NAKSHATRA = [
    ("Horse", True), ("Elephant", True), ("Sheep", False), ("Serpent", True),
    ("Serpent", False), ("Dog", False), ("Cat", False), ("Sheep", True),
    ("Cat", True), ("Rat", True), ("Rat", False), ("Cow", False),
    ("Buffalo", False), ("Tiger", False), ("Buffalo", True), ("Tiger", True),
    ("Deer", False), ("Deer", True), ("Dog", True), ("Monkey", True),
    ("Mongoose", True), ("Monkey", False), ("Lion", False), ("Horse", False),
    ("Lion", True), ("Cow", True), ("Elephant", False),
]

# Pairs at permanent enmity score nothing.
YONI_SWORN_ENEMIES = [
    ("Cow", "Tiger"), ("Elephant", "Lion"), ("Horse", "Buffalo"),
    ("Dog", "Deer"), ("Serpent", "Mongoose"), ("Monkey", "Sheep"),
    ("Cat", "Rat"),
]
# Pairs at ordinary enmity score one.
YONI_ENEMIES = [
    ("Horse", "Cow"), ("Horse", "Tiger"), ("Horse", "Deer"), ("Horse", "Lion"),
    ("Elephant", "Tiger"), ("Sheep", "Dog"), ("Sheep", "Rat"), ("Sheep", "Tiger"),
    ("Sheep", "Lion"), ("Serpent", "Cat"), ("Serpent", "Rat"), ("Serpent", "Cow"),
    ("Serpent", "Buffalo"), ("Dog", "Rat"), ("Dog", "Tiger"), ("Dog", "Mongoose"),
    ("Dog", "Lion"), ("Cat", "Tiger"), ("Cat", "Serpent"), ("Rat", "Mongoose"),
    ("Rat", "Dog"), ("Cow", "Lion"), ("Buffalo", "Tiger"), ("Buffalo", "Lion"),
    ("Tiger", "Deer"), ("Lion", "Deer"), ("Tiger", "Monkey"), ("Tiger", "Lion"), ("Monkey", "Lion"),
]
# Pairs in genuine friendship score three.
YONI_FRIENDS = [
    ("Horse", "Serpent"), ("Horse", "Monkey"), ("Horse", "Mongoose"),
    ("Elephant", "Sheep"), ("Elephant", "Serpent"), ("Elephant", "Dog"),
    ("Elephant", "Monkey"), ("Sheep", "Cow"), ("Sheep", "Buffalo"),
    ("Sheep", "Mongoose"), ("Buffalo", "Elephant"), ("Cat", "Deer"), ("Cat", "Monkey"),
    ("Cat", "Mongoose"), ("Cow", "Buffalo"), ("Cow", "Deer"),
    ("Deer", "Mongoose"), ("Monkey", "Mongoose"),
]
SAME_YONI_POINTS = 4.0
NEUTRAL_YONI_POINTS = 2.0


def _yoni_lookup() -> dict[tuple[str, str], float]:
    table: dict[tuple[str, str], float] = {}
    for points, pairs in ((0.0, YONI_SWORN_ENEMIES), (1.0, YONI_ENEMIES),
                          (3.0, YONI_FRIENDS)):
        for first, second in pairs:
            table[(first, second)] = points
            table[(second, first)] = points
    return table


YONI_POINTS = _yoni_lookup()


def yoni(boy_nakshatra: int, girl_nakshatra: int) -> tuple[str, str, float]:
    boy_animal, _ = YONI_BY_NAKSHATRA[boy_nakshatra]
    girl_animal, _ = YONI_BY_NAKSHATRA[girl_nakshatra]
    if boy_animal == girl_animal:
        score = SAME_YONI_POINTS
    else:
        score = YONI_POINTS.get((boy_animal, girl_animal), NEUTRAL_YONI_POINTS)
    return YONI_SANSKRIT[boy_animal], YONI_SANSKRIT[girl_animal], score


# --- graha maitri (5 points) --------------------------------------------------

GRAHA_MAITRI_POINTS = {
    (FRIEND, FRIEND): 5.0,
    (FRIEND, "Neutral"): 4.0,
    ("Neutral", FRIEND): 4.0,
    ("Neutral", "Neutral"): 3.0,
    (FRIEND, ENEMY): 1.0,
    (ENEMY, FRIEND): 1.0,
    ("Neutral", ENEMY): 0.5,
    (ENEMY, "Neutral"): 0.5,
    (ENEMY, ENEMY): 0.0,
}


def graha_maitri(boy_sign: int, girl_sign: int) -> tuple[str, str, float]:
    boy_lord, girl_lord = SIGN_LORDS[boy_sign], SIGN_LORDS[girl_sign]
    if boy_lord == girl_lord:
        return boy_lord, girl_lord, 5.0
    pair = (natural(boy_lord, girl_lord), natural(girl_lord, boy_lord))
    return boy_lord, girl_lord, GRAHA_MAITRI_POINTS[pair]


# --- gana (6 points) ----------------------------------------------------------

# Prokerala writes the first gana "Devata".
GANA_BY_NAKSHATRA = [
    "Devata", "Manushya", "Rakshasa", "Manushya", "Devata", "Manushya",
    "Devata", "Devata", "Rakshasa", "Rakshasa", "Manushya", "Manushya",
    "Devata", "Rakshasa", "Devata", "Rakshasa", "Devata", "Rakshasa",
    "Rakshasa", "Manushya", "Manushya", "Devata", "Rakshasa", "Rakshasa",
    "Manushya", "Manushya", "Devata",
]
# Rows the groom, columns the bride. The grid is asymmetric: a Deva groom with
# a Rakshasa bride is not the same case as the reverse.
GANA_POINTS = {
    "Devata":   {"Devata": 6.0, "Manushya": 6.0, "Rakshasa": 0.0},
    "Manushya": {"Devata": 5.0, "Manushya": 6.0, "Rakshasa": 0.0},
    "Rakshasa": {"Devata": 1.0, "Manushya": 0.0, "Rakshasa": 6.0},
}


def gana(boy_nakshatra: int, girl_nakshatra: int) -> tuple[str, str, float]:
    boy, girl = GANA_BY_NAKSHATRA[boy_nakshatra], GANA_BY_NAKSHATRA[girl_nakshatra]
    return boy, girl, GANA_POINTS[boy][girl]


# --- bhakoot (7 points) -------------------------------------------------------

# Mutual sign distances that void the koot entirely.
BHAKOOT_DOSHA_PAIRS = frozenset({(2, 12), (12, 2), (5, 9), (9, 5), (6, 8), (8, 6)})


def bhakoot(boy_sign: int, girl_sign: int) -> tuple[str, str, float]:
    forward = (girl_sign - boy_sign) % 12 + 1
    backward = (boy_sign - girl_sign) % 12 + 1
    score = 0.0 if (forward, backward) in BHAKOOT_DOSHA_PAIRS else 7.0
    return SIGNS[boy_sign], SIGNS[girl_sign], score


# --- nadi (8 points) ----------------------------------------------------------

NADI_BY_NAKSHATRA = [
    "Adi", "Madhya", "Antya", "Antya", "Madhya", "Adi",
    "Adi", "Madhya", "Antya", "Antya", "Madhya", "Adi",
    "Adi", "Madhya", "Antya", "Antya", "Madhya", "Adi",
    "Adi", "Madhya", "Antya", "Antya", "Madhya", "Adi",
    "Adi", "Madhya", "Antya",
]


def nadi(boy_nakshatra: int, girl_nakshatra: int) -> tuple[str, str, float]:
    boy, girl = NADI_BY_NAKSHATRA[boy_nakshatra], NADI_BY_NAKSHATRA[girl_nakshatra]
    return boy, girl, 0.0 if boy == girl else 8.0


# --- the whole thing ----------------------------------------------------------

KOOTS = [
    (1, "Varna", 1.0), (2, "Vasya", 2.0), (3, "Tara", 3.0), (4, "Yoni", 4.0),
    (5, "Graha Maitri", 5.0), (6, "Gana", 6.0), (7, "Bhakoot", 7.0),
    (8, "Nadi", 8.0),
]


def _moon(chart: dict) -> dict:
    moon = chart["grahas"]["Moon"]
    return {
        "sign": moon["sign_index"],
        "degree": moon["degree_in_sign"],
        "nakshatra": moon["nakshatra_index"],
        "pada": moon["nakshatra_pada"],
    }


def compute(boy_chart: dict, girl_chart: dict) -> dict:
    """Guna milan between two charts, koot by koot."""
    boy, girl = _moon(boy_chart), _moon(girl_chart)

    results = [
        varna(boy["sign"], girl["sign"]),
        vasya((boy["sign"], boy["degree"]), (girl["sign"], girl["degree"])),
        tara(boy["nakshatra"], girl["nakshatra"]),
        yoni(boy["nakshatra"], girl["nakshatra"]),
        graha_maitri(boy["sign"], girl["sign"]),
        gana(boy["nakshatra"], girl["nakshatra"]),
        bhakoot(boy["sign"], girl["sign"]),
        nadi(boy["nakshatra"], girl["nakshatra"]),
    ]

    guna = []
    total = 0.0
    for (koot_id, name, maximum), (boy_koot, girl_koot, score) in zip(KOOTS, results):
        total += score
        guna.append({
            "id": koot_id, "name": name,
            "boy_koot": boy_koot, "girl_koot": girl_koot,
            "maximum_points": maximum, "obtained_points": score,
        })

    def side(person: dict, koots: list) -> dict:
        return {
            "koot": {name.lower().replace(" ", "_"): value
                     for (_, name, _), value in zip(KOOTS, koots)},
            "nakshatra": {"index": person["nakshatra"],
                          "name": PROKERALA_NAKSHATRA_NAMES[person["nakshatra"]],
                          "name_iast": NAKSHATRAS[person["nakshatra"]],
                          "pada": person["pada"]},
            "rasi": {"index": person["sign"], "name": SIGNS[person["sign"]],
                     "name_en": SIGNS_EN[person["sign"]],
                     "lord": SIGN_LORDS[person["sign"]]},
        }

    return {
        "boy_info": side(boy, [r[0] for r in results]),
        "girl_info": side(girl, [r[1] for r in results]),
        "guna_milan": {
            "total_points": total,
            "maximum_points": MAXIMUM_POINTS,
            "guna": guna,
        },
        "nadi_dosha": results[7][2] == 0.0,
        "bhakoot_dosha": results[6][2] == 0.0,
        **provenance.MATCHING,
    }
