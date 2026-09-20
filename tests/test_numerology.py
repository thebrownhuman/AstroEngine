"""Numerology tests.

Reference values come from Prokerala's published OpenAPI examples, whose
per-letter `name_chart` identifies the inputs as JOHN DOE born 2004-02-12.
Two values were additionally confirmed by calling their live API.
"""

from datetime import date

import pytest

from astro_engine import numerology as n

JOHN = n.Name("John", "", "Doe")
BIRTH = date(2004, 2, 12)


# --- letter tables -----------------------------------------------------------

def test_pythagorean_table_matches_their_name_chart():
    expected = {"J": 1, "O": 6, "H": 8, "N": 5, "D": 4, "E": 5}
    for character, number in expected.items():
        assert n.PYTHAGOREAN[character] == number


def test_chaldean_table_matches_their_name_chart():
    expected = {"J": 1, "O": 7, "H": 5, "N": 5, "D": 4, "E": 5}
    for character, number in expected.items():
        assert n.CHALDEAN[character] == number


def test_chaldean_never_assigns_nine():
    """The defining property of the Chaldean system."""
    assert 9 not in n.CHALDEAN.values()


def test_pythagorean_is_alphabet_position_wrapped_at_nine():
    for index, character in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
        assert n.PYTHAGOREAN[character] == (index % 9) + 1


# --- reduction ---------------------------------------------------------------

@pytest.mark.parametrize("total,expected", [(35, 8), (17, 8), (18, 9), (19, 1), (9, 9)])
def test_reduction(total, expected):
    assert n.reduce_number(total) == expected


@pytest.mark.parametrize("master", [11, 22, 33])
def test_master_numbers_are_preserved(master):
    assert n.reduce_number(master) == master


@pytest.mark.parametrize("master,reduced", [(11, 2), (22, 4), (33, 6)])
def test_masters_can_be_forced_down(master, reduced):
    assert n.reduce_number(master, keep_masters=False) == reduced


def test_normalisation_folds_accents_and_drops_punctuation():
    assert n.normalise("José-María O'Brien") == "JOSEMARIAOBRIEN"


# --- values matching their published examples --------------------------------

@pytest.mark.parametrize("label,actual,expected", [
    ("life_path", n.life_path(BIRTH), 11),
    ("birthday", n.birthday_number(BIRTH), 3),
    ("birth_month", n.birth_month_number(BIRTH), 2),
    ("expression", n.expression(JOHN), 8),
    ("destiny", n.destiny(JOHN), 8),
    ("soul_urge", n.soul_urge(JOHN), 8),
    ("personality", n.personality(JOHN), 9),
    ("inner_dream", n.inner_dream(JOHN), 9),
    ("maturity", n.maturity(JOHN, BIRTH), 1),
    ("attainment", n.attainment(JOHN, BIRTH), 1),
    ("balance", n.balance(JOHN), 5),
    ("cornerstone", n.cornerstone(JOHN), 1),
    ("capstone", n.capstone(JOHN), 5),
    ("subconscious_self", n.subconscious_self(JOHN), 5),
    ("rational_thought", n.rational_thought(JOHN, BIRTH), 5),
    ("chaldean_birth", n.chaldean_birth_number(BIRTH), 3),
    ("chaldean_daily_name", n.chaldean_daily_name(JOHN), 7),
    ("chaldean_initials", n.chaldean_identity_initial_code(JOHN), 5),
    ("universal_year", n.universal_year(2004), 6),
    ("universal_month", n.universal_month(2004, 2), 8),
])
def test_matches_prokerala_example(label, actual, expected):
    assert actual == expected, label


# --- the two divergences -----------------------------------------------------

@pytest.mark.parametrize("year,month,day,expected", [
    (2004, 2, 12, 5), (1990, 1, 15, 7), (2000, 12, 31, 7),
])
def test_prokerala_universal_day_drops_the_year(year, month, day, expected):
    """Confirmed by three live API calls. Their formula ignores the year."""
    assert n.universal_day(year, month, day, prokerala_compatible=True) == expected


def test_correct_universal_day_uses_the_year():
    assert n.universal_day(2004, 2, 12) != n.universal_day(
        2004, 2, 12, prokerala_compatible=True
    )
    assert n.universal_day(2004, 2, 12) == n.reduce_number(
        n.universal_month(2004, 2) + 12
    )


@pytest.mark.parametrize("birth,expected", [(date(2004, 2, 12), 5), (date(1990, 1, 15), 7)])
def test_prokerala_chaldean_life_path_drops_the_year(birth, expected):
    """Confirmed live. Shares the year-less formula with their Universal Day."""
    assert n.chaldean_life_path(birth, prokerala_compatible=True) == expected


def test_correct_chaldean_life_path_uses_every_digit():
    assert n.chaldean_life_path(date(1990, 1, 15)) == 8  # 1+9+9+0+0+1+1+5 = 26 -> 8


# --- derived structures ------------------------------------------------------

def test_soul_urge_and_personality_partition_the_name():
    total = n.reduce_number(
        sum(x.number for x in JOHN.vowels()) + sum(x.number for x in JOHN.consonants())
    )
    assert total == n.expression(JOHN)


def test_additional_vowel_moves_y_across_the_split():
    mary = n.Name("Mary", "", "Kay")
    assert n.soul_urge(mary) != n.soul_urge(mary, additional_vowel=True)
    assert n.personality(mary) != n.personality(mary, additional_vowel=True)


def test_karmic_lessons_are_the_absent_digits():
    present = {x.number for x in JOHN.all_letters()}
    assert set(n.karmic_lessons(JOHN)) == set(range(1, 10)) - present


def test_inclusion_table_counts_every_digit():
    table = n.inclusion_table(JOHN)
    assert [row["character_value"] for row in table] == list(range(1, 10))
    assert sum(row["repeated_number_count"] for row in table) == len(JOHN.all_letters())


def test_hidden_passion_is_the_most_frequent_digit():
    counts = {}
    for letter in JOHN.all_letters():
        counts[letter.number] = counts.get(letter.number, 0) + 1
    peak = max(counts.values())
    assert set(n.hidden_passion(JOHN)) == {v for v, c in counts.items() if c == peak}


def test_pinnacles_and_challenges_cover_four_periods():
    assert len(n.pinnacles(BIRTH)) == 4
    assert len(n.challenges(BIRTH)) == 4


def test_challenges_are_never_masters():
    """Challenge numbers are differences, so they reduce all the way down."""
    for entry in n.challenges(BIRTH):
        assert 0 <= entry["number"] <= 9


def test_karmic_debt_only_flags_the_four_debt_numbers():
    for entry in n.karmic_debt(JOHN, BIRTH):
        assert entry["number"] is None or entry["number"] in n.KARMIC_DEBT_NUMBERS


def test_planes_of_expression_partition_the_alphabet():
    combined = "".join(n.PLANES.values())
    assert sorted(combined) == sorted("ABCDEFGHIJKLMNOPQRSTUVWXYZ")


# --- report ------------------------------------------------------------------

def test_report_is_deterministic():
    first = n.report(JOHN, BIRTH, reference=date(2026, 9, 20))
    second = n.report(JOHN, BIRTH, reference=date(2026, 9, 20))
    assert first == second


def test_report_records_the_mode_used():
    report = n.report(JOHN, BIRTH, reference=date(2026, 9, 20), prokerala_compatible=True)
    assert report["input"]["prokerala_compatible"] is True
    assert report["chaldean"]["life_path_number"] == 5


def test_report_includes_both_letter_tables():
    report = n.report(JOHN, BIRTH, reference=date(2026, 9, 20))
    pythagorean = report["name_chart"]["pythagorean"]["first_name"]
    chaldean = report["name_chart"]["chaldean"]["first_name"]
    assert [x["number"] for x in pythagorean] == [1, 6, 8, 5]
    assert [x["number"] for x in chaldean] == [1, 7, 5, 5]


def test_empty_middle_name_is_harmless():
    assert n.expression(n.Name("John", "", "Doe")) == n.expression(n.Name("John", last="Doe"))
