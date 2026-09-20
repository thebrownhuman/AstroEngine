"""Pythagorean and Chaldean numerology.

Both letter tables and the reduction rules were confirmed against Prokerala's
published OpenAPI examples, which include a per-letter `name_chart`. Their
worked example is JOHN DOE born 2004-02-12:

    Pythagorean  J=1 O=6 H=8 N=5 / D=4 O=6 E=5
    Chaldean     J=1 O=7 H=5 N=5 / D=4 O=7 E=5

From which destiny 35 -> 8, soul urge 17 -> 8, personality 18 -> 9, life path
2+3+6 -> 11 (master kept), maturity 11+8=19 -> 1. All match their examples.

Master numbers 11, 22 and 33 are preserved rather than reduced, which their
life path example confirms.
"""

from __future__ import annotations

import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import date

MASTER_NUMBERS = frozenset({11, 22, 33})
KARMIC_DEBT_NUMBERS = frozenset({13, 14, 16, 19})

VOWELS = frozenset("AEIOU")
# Y and W only act as vowels when the caller asks, matching Prokerala's
# `additional_vowel` parameter.
ADDITIONAL_VOWELS = frozenset("YW")

# Pythagorean: position in the alphabet, wrapped at 9.
PYTHAGOREAN = {chr(ord("A") + i): (i % 9) + 1 for i in range(26)}

# Chaldean omits 9 and does not follow alphabetical order.
CHALDEAN = {
    "A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 8, "G": 3, "H": 5, "I": 1,
    "J": 1, "K": 2, "L": 3, "M": 4, "N": 5, "O": 7, "P": 8, "Q": 1, "R": 2,
    "S": 3, "T": 4, "U": 6, "V": 6, "W": 6, "X": 5, "Y": 1, "Z": 7,
}

# Planes of expression, by the shape of each letter.
PLANES = {
    "physical": "EDMW",
    "mental": "AHJNP",
    "emotional": "BIORSTXZ",
    "intuitive": "CFGKLQUVY",
}

# Prokerala's Chaldean whole-name report splits the name into these energies.
CHALDEAN_ENERGIES = ("Domestic Energy", "Social Energy", "Sexual Energy", "Spiritual Energy")


@dataclass(frozen=True)
class Letter:
    character: str
    number: int

    def as_dict(self) -> dict:
        return {"character": self.character, "number": self.number}


def normalise(text: str) -> str:
    """Uppercase A-Z only, accents folded. Everything else is dropped."""
    folded = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in folded.upper() if "A" <= c <= "Z")


def reduce_number(total: int, keep_masters: bool = True) -> int:
    """Digit-sum down to 1-9, stopping on a master number."""
    while total > 9:
        if keep_masters and total in MASTER_NUMBERS:
            return total
        total = sum(int(d) for d in str(total))
    return total


def letters(name: str, table: dict[str, int]) -> list[Letter]:
    return [Letter(c, table[c]) for c in normalise(name)]


def is_vowel(character: str, position: int, word: str, additional_vowel: bool) -> bool:
    if character in VOWELS:
        return True
    return additional_vowel and character in ADDITIONAL_VOWELS


@dataclass(frozen=True)
class Name:
    first: str
    middle: str = ""
    last: str = ""

    @property
    def parts(self) -> dict[str, str]:
        return {"first_name": self.first, "middle_name": self.middle, "last_name": self.last}

    def chart(self, table: dict[str, int] = PYTHAGOREAN) -> dict[str, list[Letter]]:
        return {part: letters(value, table) for part, value in self.parts.items()}

    def all_letters(self, table: dict[str, int] = PYTHAGOREAN) -> list[Letter]:
        return [item for part in self.chart(table).values() for item in part]

    def vowels(self, additional_vowel: bool = False,
               table: dict[str, int] = PYTHAGOREAN) -> list[Letter]:
        out = []
        for value in self.parts.values():
            word = normalise(value)
            out += [
                Letter(c, table[c]) for i, c in enumerate(word)
                if is_vowel(c, i, word, additional_vowel)
            ]
        return out

    def consonants(self, additional_vowel: bool = False,
                   table: dict[str, int] = PYTHAGOREAN) -> list[Letter]:
        out = []
        for value in self.parts.values():
            word = normalise(value)
            out += [
                Letter(c, table[c]) for i, c in enumerate(word)
                if not is_vowel(c, i, word, additional_vowel)
            ]
        return out

    def initials(self, table: dict[str, int] = PYTHAGOREAN) -> list[Letter]:
        return [
            Letter(normalise(v)[0], table[normalise(v)[0]])
            for v in self.parts.values() if normalise(v)
        ]


def _total(items: list[Letter]) -> int:
    return sum(item.number for item in items)


def _chart_dict(name: Name, table: dict[str, int]) -> dict:
    return {
        part: [letter.as_dict() for letter in items]
        for part, items in name.chart(table).items()
    }


# --- date-derived numbers ----------------------------------------------------

def life_path(birth: date) -> int:
    """Month, day and year reduced separately, then summed and reduced.

    Verified: 2004-02-12 gives 2 + 3 + 6 = 11, kept as a master number.
    """
    return reduce_number(
        reduce_number(birth.month) + reduce_number(birth.day) + reduce_number(birth.year)
    )


def birthday_number(birth: date) -> int:
    return reduce_number(birth.day)


def birth_month_number(birth: date) -> int:
    return reduce_number(birth.month)


def universal_year(year: int) -> int:
    return reduce_number(year)


def universal_month(year: int, month: int) -> int:
    return reduce_number(universal_year(year) + month)


def universal_day(year: int, month: int, day: int,
                  prokerala_compatible: bool = False) -> int:
    """Universal Day builds on the Universal Month.

    Prokerala instead computes reduce(reduce(month) + reduce(day)), dropping the
    year entirely. Confirmed against their API on three dates:

        2004-02-12 -> 5 = 2 + 3
        1990-01-15 -> 7 = 1 + 6
        2000-12-31 -> 7 = 3 + 4

    A universal day that ignores the year is not a universal day, so this is off
    by default.
    """
    if prokerala_compatible:
        return reduce_number(reduce_number(month) + reduce_number(day))
    return reduce_number(universal_month(year, month) + day)


def personal_year(birth: date, reference_year: int) -> int:
    return reduce_number(
        reduce_number(birth.month) + reduce_number(birth.day)
        + reduce_number(reference_year)
    )


def personal_month(birth: date, reference: date) -> int:
    return reduce_number(personal_year(birth, reference.year) + reference.month)


def personal_day(birth: date, reference: date) -> int:
    return reduce_number(personal_month(birth, reference) + reference.day)


def pinnacles(birth: date) -> list[dict]:
    month, day, year = (reduce_number(x) for x in (birth.month, birth.day, birth.year))
    first = reduce_number(month + day)
    second = reduce_number(day + year)
    third = reduce_number(first + second)
    fourth = reduce_number(month + year)
    # Pinnacle boundaries hang off the Life Path.
    start = 36 - reduce_number(life_path(birth), keep_masters=False)
    spans = [f"0-{start}", f"{start + 1}-{start + 9}",
             f"{start + 10}-{start + 18}", f"{start + 19}+"]
    names = ("First Pinnacle", "Second Pinnacle", "Third Pinnacle", "Fourth Pinnacle")
    return [
        {"name": n, "age": a, "number": v}
        for n, a, v in zip(names, spans, (first, second, third, fourth))
    ]


def challenges(birth: date) -> list[dict]:
    month, day, year = (
        reduce_number(x, keep_masters=False) for x in (birth.month, birth.day, birth.year)
    )
    first = abs(month - day)
    second = abs(day - year)
    third = abs(first - second)
    fourth = abs(month - year)
    start = 36 - reduce_number(life_path(birth), keep_masters=False)
    spans = [f"0-{start}", f"{start + 1}-{start + 9}",
             f"{start + 10}-{start + 18}", f"{start + 19}+"]
    names = ("First Challenge", "Second Challenge", "Third Challenge", "Fourth Challenge")
    return [
        {"name": n, "age": a, "number": reduce_number(v, keep_masters=False)}
        for n, a, v in zip(names, spans, (first, second, third, fourth))
    ]


def period_cycles(birth: date) -> list[dict]:
    return [
        {"name": "Birth Month", "number": reduce_number(birth.month)},
        {"name": "Birth Day", "number": reduce_number(birth.day)},
        {"name": "Birth Year", "number": reduce_number(birth.year)},
    ]


# --- name-derived numbers ----------------------------------------------------

def expression(name: Name) -> int:
    """Every letter of the full name. Destiny is the same number."""
    return reduce_number(_total(name.all_letters()))


destiny = expression


def soul_urge(name: Name, additional_vowel: bool = False) -> int:
    return reduce_number(_total(name.vowels(additional_vowel)))


def personality(name: Name, additional_vowel: bool = False) -> int:
    return reduce_number(_total(name.consonants(additional_vowel)))


inner_dream = personality


def balance(name: Name) -> int:
    return reduce_number(_total(name.initials()))


def cornerstone(name: Name) -> int:
    return PYTHAGOREAN[normalise(name.first)[0]]


def capstone(name: Name) -> int:
    return PYTHAGOREAN[normalise(name.first)[-1]]


def maturity(name: Name, birth: date) -> int:
    """Life Path plus Expression. Attainment is the same number."""
    return reduce_number(life_path(birth) + expression(name))


attainment = maturity


def rational_thought(name: Name, birth: date) -> int:
    return reduce_number(_total(letters(name.first, PYTHAGOREAN)) + birth.day)


def inclusion_table(name: Name) -> list[dict]:
    counts = Counter(item.number for item in name.all_letters())
    return [
        {"character_value": value, "repeated_number_count": counts.get(value, 0)}
        for value in range(1, 10)
    ]


def karmic_lessons(name: Name) -> list[int]:
    present = {item.number for item in name.all_letters()}
    return [value for value in range(1, 10) if value not in present]


def subconscious_self(name: Name) -> int:
    return 9 - len(karmic_lessons(name))


def hidden_passion(name: Name) -> list[int]:
    counts = Counter(item.number for item in name.all_letters())
    if not counts:
        return []
    peak = max(counts.values())
    return sorted(v for v, c in counts.items() if c == peak)


def planes_of_expression(name: Name) -> list[dict]:
    text = "".join(normalise(v) for v in name.parts.values())
    out = []
    for plane, group in PLANES.items():
        total = sum(PYTHAGOREAN[c] for c in text if c in group)
        out.append({
            "name": f"{plane.title()} Planes of Expression",
            "number": reduce_number(total) if total else 0,
        })
    return out


def karmic_debt(name: Name, birth: date, additional_vowel: bool = False) -> list[dict]:
    """A karmic debt is flagged when an unreduced total is 13, 14, 16 or 19."""
    raw = {
        "Life Path Number": reduce_number(birth.month) + reduce_number(birth.day)
        + reduce_number(birth.year),
        "Expression Number": _total(name.all_letters()),
        "Soul Urge Number": _total(name.vowels(additional_vowel)),
        "Personality Number": _total(name.consonants(additional_vowel)),
        "Birthday Number": birth.day,
    }
    return [
        {"name": label, "number": total if total in KARMIC_DEBT_NUMBERS else None}
        for label, total in raw.items()
    ]


def bridge_numbers(name: Name, birth: date, additional_vowel: bool = False) -> list[dict]:
    pairs = (
        ("Expression / Heart Desire Number", expression(name),
         soul_urge(name, additional_vowel)),
        ("Life Path / Expression Number", life_path(birth), expression(name)),
        ("Heart Desire / Personality Number", soul_urge(name, additional_vowel),
         personality(name, additional_vowel)),
        ("Life Path / Heart Desire Number", life_path(birth),
         soul_urge(name, additional_vowel)),
    )
    return [{"name": label, "number": abs(a - b)} for label, a, b in pairs]


# --- Chaldean ----------------------------------------------------------------

def chaldean_birth_number(birth: date) -> int:
    return reduce_number(birth.day, keep_masters=False)


def chaldean_life_path(birth: date, prokerala_compatible: bool = False) -> int:
    """Every digit of the date, summed and reduced with no master exception.

    Prokerala returns reduce(reduce(month) + reduce(day)) here - the same
    year-less formula as their Universal Day, which the two endpoints appear to
    share. Verified on 2004-02-12 (5) and 1990-01-15 (7). A life path that
    ignores the birth year is not a life path, so this is off by default.
    """
    if prokerala_compatible:
        return reduce_number(
            reduce_number(birth.month) + reduce_number(birth.day), keep_masters=False
        )
    digits = f"{birth.year:04d}{birth.month:02d}{birth.day:02d}"
    return reduce_number(sum(int(d) for d in digits), keep_masters=False)


def chaldean_name_number(name: Name) -> int:
    return reduce_number(_total(name.all_letters(CHALDEAN)), keep_masters=False)


chaldean_daily_name = chaldean_name_number


def chaldean_identity_initial_code(name: Name) -> int:
    return reduce_number(_total(name.initials(CHALDEAN)), keep_masters=False)


def chaldean_whole_name(name: Name) -> list[dict]:
    """Per-name-part energies, in Prokerala's order."""
    values = [
        reduce_number(_total(letters(part, CHALDEAN)), keep_masters=False)
        for part in name.parts.values() if normalise(part)
    ]
    whole = chaldean_name_number(name)
    values = (values + [whole])[: len(CHALDEAN_ENERGIES)]
    return [
        {"name": label, "number": value}
        for label, value in zip(CHALDEAN_ENERGIES, values)
    ]


# --- assembled report --------------------------------------------------------

def report(
    name: Name,
    birth: date,
    reference: date | None = None,
    additional_vowel: bool = False,
    prokerala_compatible: bool = False,
) -> dict:
    """Everything in one call, so an LLM never has to do arithmetic.

    `prokerala_compatible` reproduces two quirks in their implementation: the
    Universal Day and Chaldean Life Path both drop the year. Everything else
    already matches them exactly.
    """
    reference = reference or date.today()
    return {
        "input": {
            "first_name": name.first,
            "middle_name": name.middle,
            "last_name": name.last,
            "date_of_birth": birth.isoformat(),
            "reference_date": reference.isoformat(),
            "additional_vowel": additional_vowel,
            "prokerala_compatible": prokerala_compatible,
        },
        "name_chart": {
            "pythagorean": _chart_dict(name, PYTHAGOREAN),
            "chaldean": _chart_dict(name, CHALDEAN),
        },
        "pythagorean": {
            "life_path_number": life_path(birth),
            "birthday_number": birthday_number(birth),
            "birth_month_number": birth_month_number(birth),
            "expression_number": expression(name),
            "destiny_number": destiny(name),
            "soul_urge_number": soul_urge(name, additional_vowel),
            "personality_number": personality(name, additional_vowel),
            "inner_dream_number": inner_dream(name, additional_vowel),
            "maturity_number": maturity(name, birth),
            "attainment_number": attainment(name, birth),
            "balance_number": balance(name),
            "cornerstone_number": cornerstone(name),
            "capstone_number": capstone(name),
            "rational_thought_number": rational_thought(name, birth),
            "subconscious_self_number": subconscious_self(name),
            "hidden_passion_number": hidden_passion(name),
            "karmic_lesson_numbers": karmic_lessons(name),
            "inclusion_table": inclusion_table(name),
            "planes_of_expression": planes_of_expression(name),
            "karmic_debt": karmic_debt(name, birth, additional_vowel),
            "bridge_numbers": bridge_numbers(name, birth, additional_vowel),
            "pinnacles": pinnacles(birth),
            "challenges": challenges(birth),
            "period_cycles": period_cycles(birth),
            "personal_year_number": personal_year(birth, reference.year),
            "personal_month_number": personal_month(birth, reference),
            "personal_day_number": personal_day(birth, reference),
            "universal_year_number": universal_year(reference.year),
            "universal_month_number": universal_month(reference.year, reference.month),
            "universal_day_number": universal_day(
                reference.year, reference.month, reference.day, prokerala_compatible
            ),
        },
        "chaldean": {
            "birth_number": chaldean_birth_number(birth),
            "life_path_number": chaldean_life_path(birth, prokerala_compatible),
            "daily_name_number": chaldean_daily_name(name),
            "identity_initial_code_number": chaldean_identity_initial_code(name),
            "whole_name_number": chaldean_whole_name(name),
        },
    }
